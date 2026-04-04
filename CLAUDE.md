# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Polymarket 15-minute arbitrage bot. Buys both sides (UP + DOWN) of crypto prediction markets when total cost < $1.00, locking in guaranteed profit. Supports BTC, ETH, SOL, BNB, DOGE, XRP markets running in parallel via asyncio.

## Commands

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run (multi-market, recommended)
python -m src.multi_market_bot

# Run (single market)
python -m src.simple_arb_bot

# Run all tests
pytest

# Run a single test file
pytest tests/test_arbitrage.py

# Run a single test class or method
pytest tests/test_arbitrage.py::TestArbitrageDetection -v

# Run integration tests only
pytest -m integration

# Diagnostic utilities
python -m src.test_balance
python -m src.diagnose_config
python -m src.generate_api_key
```

## Architecture

**Entry points:** `src/multi_market_bot.py` (orchestrator) and `src/simple_arb_bot.py` (single-market bot).

`MultiMarketBot` auto-detects active markets via HTTP, launches a `SimpleArbitrageBot` per market, and refreshes the market list every 60s. Each bot runs its own async loop.

**Hot path (~156ms):** WSS price update (5ms) → `check_arbitrage()` (1ms) → `place_orders_fast()` + crypto signing (150ms). Balance is cached in background to avoid blocking.

**Key modules:**
- `simple_arb_bot.py` — Core arbitrage detection and execution. `check_arbitrage()` computes fills from order book; `execute_arbitrage_async()` places both legs.
- `trading.py` — Order placement via `py-clob-client`, fill verification, balance queries. `place_orders_fast()` pre-signs and submits both orders in a single HTTP request.
- `wss_market.py` — WebSocket client for CLOB order book updates. Uses dirty-flag caching on `L2BookState` to avoid rebuilding sorted levels on every tick.
- `lookup.py` — Resolves market slugs to token IDs via Polymarket Gamma API.
- `risk_manager.py` — Guards: daily loss limit, position size, trade count, min balance, utilization cap.
- `shared_rate_limiter.py` — File-lock based rate limiter (`/tmp/polymarket_rate_state.json`) shared with external Rust `pm_bot`. 80 req/60s window.
- `config.py` — `Settings` dataclass loaded from env vars / `.env` file.
- `statistics.py` — `TradeRecord` and `PerformanceStats` tracking.

**Key patterns:**
- Deal deduplication: 10s window keyed on `{market_slug}:{price_up}:{price_down}` prevents re-entry into same opportunity.
- FOK orders skip fill polling (filled-or-killed at submission). GTC/FAK orders poll with timeout.
- Partial fill unwind: if only one leg fills, the bot sells at best bid.
- `asyncio.to_thread()` wraps blocking `py-clob-client` calls to keep the event loop responsive.

## Configuration

All config via environment variables (or `.env` file). See `.env.example` for the full template. Required: `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_API_KEY`, `POLYMARKET_API_SECRET`, `POLYMARKET_API_PASSPHRASE`.

Key trading params: `TARGET_PAIR_COST` (arb threshold, default 0.99), `ORDER_SIZE`, `ORDER_TYPE` (FOK|FAK|GTC), `DRY_RUN`.

**Wallet signature types** (`POLYMARKET_SIGNATURE_TYPE`):
- `0` ��� EOA (direct wallet, no proxy). Rare on Polymarket.
- `1` — POLY_PROXY (Magic Link / email login). Requires `POLYMARKET_FUNDER`.
- `2` — POLY_GNOSIS_SAFE (MetaMask users, **most common**). Requires `POLYMARKET_FUNDER` set to the proxy wallet address shown on your Polymarket profile. Default.

Use the Polymarket profile API to confirm your proxy wallet: `GET https://gamma-api.polymarket.com/public-profile?address=<your_signer_address>` — the `proxyWallet` field is your `POLYMARKET_FUNDER`.

## Testing

Tests use pytest with `conftest.py` adding `src/` to `sys.path`. Integration tests are marked with `@pytest.mark.integration`. No CI pipeline is configured — tests run locally only.
