"""
Rate limiter partilhado entre pm_bot (Rust) e arb_bot (Python).

Usa um ficheiro JSON como mutex de baixa frequência.
O pm_bot Rust deve ler/escrever o mesmo ficheiro.

Formato do ficheiro:
{
 "window_start_s": 1234567890.0,
 "requests_in_window": 42,
 "max_per_window": 100,
 "window_size_s": 60,
 "last_writer": "arb_bot" // ou "pm_bot"
}
"""

import json
import os
import time
import fcntl
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Caminho partilhado — deve ser o mesmo no Rust
RATE_STATE_PATH = os.getenv(
    "SHARED_RATE_STATE_PATH",
    "/tmp/polymarket_rate_state.json"
)

# Configuração de rate limit (ajustar ao limite real da API)
MAX_REQUESTS_PER_WINDOW = int(os.getenv("RATE_LIMIT_MAX", "100"))
WINDOW_SIZE_S = float(os.getenv("RATE_LIMIT_WINDOW_S", "60.0"))


class SharedRateLimiter:
    """
    Rate limiter partilhado via ficheiro entre pm_bot e arb_bot.
    
    Thread-safe via fcntl locks.
    Não bloqueia — retorna False se o rate limit foi atingido.
    """

    def __init__(
        self,
        state_path: str = RATE_STATE_PATH,
        max_per_window: int = MAX_REQUESTS_PER_WINDOW,
        window_size_s: float = WINDOW_SIZE_S,
        writer_name: str = "arb_bot",
    ):
        self.state_path = state_path
        self.max_per_window = max_per_window
        self.window_size_s = window_size_s
        self.writer_name = writer_name
        self._local_count = 0  # fallback se ficheiro não disponível

    def _read_state(self, f) -> dict:
        """Lê estado do ficheiro (com lock já adquirido)."""
        try:
            f.seek(0)
            content = f.read()
            if content:
                return json.loads(content)
        except Exception:
            pass
        return {
            "window_start_s": time.time(),
            "requests_in_window": 0,
            "max_per_window": self.max_per_window,
            "window_size_s": self.window_size_s,
            "last_writer": self.writer_name,
        }

    def _write_state(self, f, state: dict) -> None:
        """Escreve estado no ficheiro (com lock já adquirido)."""
        f.seek(0)
        f.truncate()
        json.dump(state, f)
        f.flush()

    def check_and_increment(self) -> bool:
        """
        Verifica se pode fazer um request e incrementa o contador.
        
        Returns:
            True se pode prosseguir
            False se rate limit atingido
        """
        try:
            with open(self.state_path, "a+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    state = self._read_state(f)
                    now = time.time()
                    
                    # Reset janela se expirou
                    if now - state["window_start_s"] > self.window_size_s:
                        state["window_start_s"] = now
                        state["requests_in_window"] = 0
                    
                    # Verificar limite
                    if state["requests_in_window"] >= self.max_per_window:
                        remaining = self.window_size_s - (now - state["window_start_s"])
                        logger.warning(
                            f"Rate limit partilhado atingido: "
                            f"{state['requests_in_window']}/{self.max_per_window} "
                            f"(reset em {remaining:.1f}s)"
                        )
                        return False
                    
                    # Incrementar
                    state["requests_in_window"] += 1
                    state["last_writer"] = self.writer_name
                    self._write_state(f, state)
                    return True
                
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        
        except Exception as e:
            logger.debug(f"Rate limiter ficheiro indisponível: {e} — usando fallback local")
            # Fallback: rate limit local simples
            self._local_count += 1
            return self._local_count <= self.max_per_window

    def get_stats(self) -> dict:
        """Retorna estatísticas actuais do rate limiter."""
        try:
            with open(self.state_path, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return self._read_state(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            return {"requests_in_window": self._local_count}


# Instância global — importar noutros módulos
_rate_limiter: Optional[SharedRateLimiter] = None


def get_rate_limiter() -> SharedRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SharedRateLimiter()
    return _rate_limiter
