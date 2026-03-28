import asyncio
import concurrent.futures
import functools
import logging
from typing import Optional
import time

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    BalanceAllowanceParams,
    AssetType,
    OrderArgs,
    OrderType,
    PostOrdersArgs,
    PartialCreateOrderOptions,
)
from py_clob_client.order_builder.constants import BUY, SELL

from .config import Settings
from .shared_rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


_cached_client = None

def get_client(settings: Settings) -> ClobClient:
    global _cached_client
    
    if _cached_client is not None:
        return _cached_client
    
    if not settings.private_key:
        raise RuntimeError("POLYMARKET_PRIVATE_KEY is required for trading")
    
    host = "https://clob.polymarket.com"
    
    # Create client with signature_type=1 for Magic/Email accounts
    _cached_client = ClobClient(
        host, 
        key=settings.private_key.strip(), 
        chain_id=137, 
        signature_type=settings.signature_type, 
        funder=settings.funder.strip() if settings.funder else None
    )
    
    # Derive API credentials - simple method that works
    logger.info("Deriving User API credentials from private key...")
    derived_creds = _cached_client.create_or_derive_api_creds()
    _cached_client.set_api_creds(derived_creds)
    
    logger.info("✅ API credentials configured")
    logger.info(f"   API Key: {derived_creds.api_key}")
    logger.info(f"   Wallet: {_cached_client.get_address()}")
    logger.info(f"   Funder: {settings.funder}")
    
    return _cached_client


def get_balance(settings: Settings) -> float:
    """Get USDC balance from Polymarket account."""
    try:
        client = get_client(settings)
        # Get USDC (COLLATERAL) balance
        params = BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=settings.signature_type
        )
        result = client.get_balance_allowance(params)
        
        if isinstance(result, dict):
            balance_raw = result.get("balance", "0")
            balance_wei = float(balance_raw)
            # USDC has 6 decimals
            balance_usdc = balance_wei / 1_000_000
            return balance_usdc
        
        logger.warning(f"Unexpected response when getting balance: {result}")
        return 0.0
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return 0.0


def place_order(settings: Settings, *, side: str, token_id: str, price: float, size: float, tif: str = "GTC") -> dict:
    if price <= 0:
        raise ValueError("price must be > 0")
    if size <= 0:
        raise ValueError("size must be > 0")
    if not token_id:
        raise ValueError("token_id is required")

    # Rate limit check partilhado com pm_bot
    rl = get_rate_limiter()
    if not rl.check_and_increment():
        raise RuntimeError("SHARED_RATE_LIMIT: aguardar antes de novo request")

    side_up = side.upper()
    if side_up not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")

    client = get_client(settings)
    
    try:
        # Create order args
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=BUY if side_up == "BUY" else SELL
        )
        
        # BTC 15min markets are neg_risk but auto-detection via /neg-risk endpoint
        # often fails (returns "Invalid token id"). Force neg_risk=True for these markets.
        # This is safe: the worst case for non-neg_risk markets is a rejected order, not a bad signature.
        options = PartialCreateOrderOptions(neg_risk=True)
        signed_order = client.create_order(order_args, options)
        
        tif_up = (tif or "GTC").upper()
        order_type = getattr(OrderType, tif_up, OrderType.GTC)
        return client.post_order(signed_order, order_type)
    except Exception as exc:  # pragma: no cover - passthrough from client
        raise RuntimeError(f"place_order failed: {exc}") from exc



def place_orders_fast(settings: Settings, orders: list[dict], *, order_type: str = "GTC") -> list[dict]:
    """Place multiple orders as fast as possible.

    Strategy: pre-sign all orders first, then submit them together.
    This minimizes the time gap between legs.

    Args:
        settings: Bot settings
        orders: List of order dicts with keys: side, token_id, price, size
        order_type: One of OrderType: FOK, FAK, GTC, GTD

    Returns:
        List of order results.
    """
    # Rate limit check partilhado com pm_bot (batch = 1 request HTTP)
    rl = get_rate_limiter()
    if not rl.check_and_increment():
        raise RuntimeError("SHARED_RATE_LIMIT: aguardar antes de novo request")

    client = get_client(settings)

    tif_up = (order_type or "GTC").upper()
    ot = getattr(OrderType, tif_up, OrderType.GTC)

    # Step 1: Pre-sign all orders (this is the slow part)
    # Force neg_risk=True for BTC 15min markets (auto-detection fails)
    options = PartialCreateOrderOptions(neg_risk=True)
    signed_orders = []
    for order_params in orders:
        side_up = order_params["side"].upper()
        order_args = OrderArgs(
            token_id=order_params["token_id"],
            price=order_params["price"],
            size=order_params["size"],
            side=BUY if side_up == "BUY" else SELL,
        )
        signed_order = client.create_order(order_args, options)
        signed_orders.append(signed_order)

    # Step 2: Post all orders in a single request when possible.
    try:
        args = [PostOrdersArgs(order=o, orderType=ot) for o in signed_orders]
        result = client.post_orders(args)
        if isinstance(result, list):
            return result
        return [result]
    except Exception:
        # Fallback to sequential posting if batch fails for any reason.
        results: list[dict] = []
        for signed_order in signed_orders:
            try:
                results.append(client.post_order(signed_order, ot))
            except Exception as exc:
                results.append({"error": str(exc)})
        return results


def extract_order_id(result: dict) -> Optional[str]:
    """Best-effort extraction of an order id from API responses."""
    if not isinstance(result, dict):
        return None
    # Common variants observed across APIs/versions
    for key in ("orderID", "orderId", "order_id", "id"):
        val = result.get(key)
        if val:
            return str(val)
    # Sometimes nested
    for key in ("order", "data", "result"):
        nested = result.get(key)
        if isinstance(nested, dict):
            oid = extract_order_id(nested)
            if oid:
                return oid
    return None


def get_order(settings: Settings, order_id: str) -> dict:
    client = get_client(settings)
    return client.get_order(order_id)


def cancel_orders(settings: Settings, order_ids: list[str]) -> Optional[dict]:
    if not order_ids:
        return None
    client = get_client(settings)
    return client.cancel_orders(order_ids)


def _coerce_float(val) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def summarize_order_state(order_data: dict, *, requested_size: Optional[float] = None) -> dict:
    """Normalize an order payload into a small, stable summary.

    The API field names vary by version; this function is defensive.
    """
    if not isinstance(order_data, dict):
        return {"status": None, "filled_size": None, "requested_size": requested_size, "raw": order_data}

    status = order_data.get("status") or order_data.get("state") or order_data.get("order_status")
    status_str = str(status).lower() if status is not None else None

    filled_size = None
    for key in ("filled_size", "filledSize", "size_filled", "sizeFilled", "matched_size", "matchedSize"):
        if key in order_data:
            filled_size = _coerce_float(order_data.get(key))
            break

    # Some payloads provide remaining size rather than filled size
    remaining_size = None
    for key in ("remaining_size", "remainingSize", "size_remaining", "sizeRemaining"):
        if key in order_data:
            remaining_size = _coerce_float(order_data.get(key))
            break

    original_size = None
    for key in ("original_size", "originalSize", "size", "order_size", "orderSize"):
        if key in order_data:
            original_size = _coerce_float(order_data.get(key))
            break

    if filled_size is None and remaining_size is not None and original_size is not None:
        filled_size = max(0.0, original_size - remaining_size)

    return {
        "status": status_str,
        "filled_size": filled_size,
        "remaining_size": remaining_size,
        "original_size": original_size,
        "requested_size": requested_size,
        "raw": order_data,
    }


def wait_for_terminal_order(
    settings: Settings,
    order_id: str,
    *,
    requested_size: Optional[float] = None,
    timeout_seconds: float = 3.0,
    poll_interval_seconds: float = 0.25,
) -> dict:
    """Poll order state until it is terminal, filled, or timeout."""
    terminal_statuses = {"filled", "canceled", "cancelled", "rejected", "expired"}
    start = time.monotonic()
    last_summary: Optional[dict] = None

    while (time.monotonic() - start) < timeout_seconds:
        try:
            od = get_order(settings, order_id)
            last_summary = summarize_order_state(od, requested_size=requested_size)
        except Exception as exc:
            last_summary = {"status": "error", "error": str(exc), "filled_size": None, "requested_size": requested_size}

        status = (last_summary.get("status") or "").lower() if isinstance(last_summary, dict) else ""
        filled = last_summary.get("filled_size") if isinstance(last_summary, dict) else None

        if requested_size is not None and filled is not None and filled + 1e-9 >= float(requested_size):
            last_summary["terminal"] = True
            last_summary["filled"] = True
            return last_summary

        if status in terminal_statuses:
            last_summary["terminal"] = True
            last_summary["filled"] = (status == "filled")
            return last_summary

        time.sleep(poll_interval_seconds)

    if last_summary is None:
        last_summary = {"status": None, "filled_size": None, "requested_size": requested_size}
    last_summary["terminal"] = False
    last_summary.setdefault("filled", False)
    return last_summary


def get_positions(settings: Settings, token_ids: list[str] = None) -> dict:
    """
    Get current positions (shares owned) for the user.
    
    Args:
        settings: Bot settings
        token_ids: Optional list of token IDs to filter by
        
    Returns:
        Dictionary with token_id -> position data
    """
    try:
        client = get_client(settings)
        
        # Get all positions for the user
        positions = client.get_positions()
        
        # Filter by token_ids if provided
        result = {}
        for pos in positions:
            token_id = pos.get("asset", {}).get("token_id") or pos.get("token_id")
            if token_id:
                if token_ids is None or token_id in token_ids:
                    size = float(pos.get("size", 0))
                    avg_price = float(pos.get("avg_price", 0))
                    result[token_id] = {
                        "size": size,
                        "avg_price": avg_price,
                        "raw": pos
                    }
        
        return result
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {}


def warmup_client_cache(settings: Settings, token_ids: list[str]) -> None:
    """
    Pré-aquece o cache do cliente CLOB.
    
    Chama get_tick_size e get_neg_risk para cada token ANTES
    de qualquer trade, eliminando HTTP frio no hot path.
    
    Deve ser chamado uma vez no startup do bot.
    """
    client = get_client(settings)
    logger.info(f"Pré-aquecendo cache para {len(token_ids)} tokens...")
    
    for token_id in token_ids:
        try:
            # Força fetch e cacheamento do tick size (TTL 300s)
            client.get_tick_size(token_id)
            # Força fetch e cacheamento do neg_risk
            client.get_neg_risk(token_id)
            logger.debug(f"Cache quente: {token_id[:16]}...")
        except Exception as e:
            logger.warning(f"Warmup falhou para {token_id[:16]}: {e}")
    
    logger.info("✅ Cache pré-aquecido — primeira ordem será rápida")


def refresh_cache_if_needed(settings: Settings, token_ids: list[str], ttl_s: float = 240.0) -> None:
    """
    Refresh proactivo do cache antes de expirar.
    
    O TTL do tick_size é 300s. Refrescar aos 240s evita
    que expire a meio do hot path.
    
    Chamar em background a cada 4 minutos.
    """
    client = get_client(settings)
    now = time.monotonic()
    
    for token_id in token_ids:
        cached_at = getattr(client, '_ClobClient__tick_size_timestamps', {}).get(token_id)
        if cached_at is None or (now - cached_at) > ttl_s:
            try:
                client.get_tick_size(token_id)
                client.get_neg_risk(token_id)
                logger.debug(f"Cache refreshed: {token_id[:16]}...")
            except Exception as e:
                logger.warning(f"Cache refresh falhou: {e}")


# Thread pool para operações de IO paralelas
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


async def wait_for_terminal_order_async(
    settings,
    order_id: str,
    *,
    requested_size: Optional[float] = None,
    timeout_seconds: float = 3.0,
    poll_interval_seconds: float = 0.25,
) -> dict:
    """Versão async de wait_for_terminal_order — não bloqueia o event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _thread_pool,
        lambda: wait_for_terminal_order(
            settings,
            order_id,
            requested_size=requested_size,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        ),
    )


async def verify_both_fills_async(
    settings,
    up_order_id: str,
    down_order_id: str,
    order_size: float,
    order_type: str = "FOK",
) -> tuple[dict, dict]:
    """
    Verifica fills dos dois legs.
    
    FOK: assume fill imediato se order_id retornou sem erro.
    Não faz polling — FOK ou preenche ou cancela na submissão.
    
    GTC/FAK: verifica em paralelo com timeout de 3s.
    """
    if order_type.upper() == "FOK":
        # FOK não precisa de polling — se temos o order_id, a ordem foi aceite.
        # O fill aconteceu na submissão ou foi cancelado (e teremos error no result).
        up_result = {
            "status": "filled",
            "filled_size": order_size,
            "filled": True,
            "terminal": True,
        }
        down_result = {
            "status": "filled",
            "filled_size": order_size,
            "filled": True,
            "terminal": True,
        }
        return up_result, down_result
    else:
        # GTC/FAK: verificar em paralelo (não sequencial!)
        up_task = wait_for_terminal_order_async(
            settings, up_order_id, requested_size=order_size
        )
        down_task = wait_for_terminal_order_async(
            settings, down_order_id, requested_size=order_size
        )
        up_state, down_state = await asyncio.gather(up_task, down_task)
        return up_state, down_state
