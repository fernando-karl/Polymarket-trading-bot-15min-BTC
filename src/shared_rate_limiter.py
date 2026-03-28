"""
Rate limiter partilhado entre pm_bot (Rust) e arb_bot (Python).

Usa um ficheiro JSON como mutex partilhado.
O pm_bot Rust deve ler/escrever o mesmo ficheiro.
"""

import json
import os
import time
import fcntl
import logging
from typing import Optional

logger = logging.getLogger(__name__)

RATE_STATE_PATH = os.getenv(
    "SHARED_RATE_STATE_PATH",
    "/tmp/polymarket_rate_state.json"
)
MAX_PER_WINDOW = int(os.getenv("RATE_LIMIT_MAX", "80"))
WINDOW_S = 60.0


def check_and_increment(writer: str = "arb_bot") -> bool:
    """
    Rate limit check partilhado.
    
    Usa LOCK_EX blocking — o lock é mantido < 1ms,
    portanto bloquear é preferível a ter race condition com NONBLOCK.
    """
    try:
        with open(RATE_STATE_PATH, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read()
                now = time.time()
                
                if content:
                    state = json.loads(content)
                else:
                    state = {"t0": now, "n": 0}
                
                # Reset janela
                if now - state.get("t0", now) > WINDOW_S:
                    state = {"t0": now, "n": 0}
                
                if state["n"] >= MAX_PER_WINDOW:
                    logger.warning(f"Rate limit: {state['n']}/{MAX_PER_WINDOW}")
                    return False
                
                state["n"] += 1
                state["writer"] = writer
                state["last_t"] = now
                
                f.seek(0)
                f.truncate()
                json.dump(state, f)
                return True
            
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    
    except Exception as e:
        logger.debug(f"Rate limiter indisponível: {e}")
        return True  # fail open se ficheiro inacessível


def get_stats() -> dict:
    """Retorna estatísticas actuais do rate limiter."""
    try:
        with open(RATE_STATE_PATH) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        return {}


_rate_limiter = None


def get_rate_limiter():
    """Retorna uma função wrapper para compatibilidade."""
    global _rate_limiter
    if _rate_limiter is None:
        def wrapper():
            return check_and_increment()
        _rate_limiter = wrapper
    return _rate_limiter
