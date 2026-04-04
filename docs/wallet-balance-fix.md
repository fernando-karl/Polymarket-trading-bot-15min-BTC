# Wallet Balance Diagnosis Fix

**Date:** 2026-04-04
**Issue:** Bot reported $0 balance despite $26.97 available in Polymarket UI

## Root Cause

`POLYMARKET_SIGNATURE_TYPE` was set to `0` (EOA) in `.env`, and all code defaults used `0` or `1`. The actual account type is **Gnosis Safe** (`signature_type=2`), which is what Polymarket assigns to MetaMask users.

Polymarket uses three signature types:

| Type | Name | Used By |
|------|------|---------|
| 0 | EOA | Direct wallet control (rare on Polymarket) |
| 1 | POLY_PROXY | Magic Link / email login users |
| 2 | POLY_GNOSIS_SAFE | MetaMask and other browser wallet users |

With the wrong signature type, the CLOB API queries the balance for the wrong address and returns $0 — without any error message. This made it impossible to distinguish "no funds" from "wrong configuration" using the existing diagnostics.

## Diagnosis Process

1. **CLOB API** returned `$0.00` with no error for both `signature_type=0` and `signature_type=1`
2. **On-chain RPC checks** initially showed $0 everywhere because `polygon-rpc.com` was returning errors silently — switching to `polygon-bor-rpc.publicnode.com` revealed $20.97 USDC on the signer and $26.97 USDC.e on the proxy wallet
3. **Polymarket Profile API** (`GET https://gamma-api.polymarket.com/public-profile?address=<addr>`) confirmed both addresses map to the same account and returned the `proxyWallet` address
4. Testing all three signature types against the CLOB balance endpoint found that only `signature_type=2` returned the correct $26.97 balance

## Changes Made

### 1. `.env` — Fixed signature type

```
POLYMARKET_SIGNATURE_TYPE=2
```

### 2. `src/config.py` — Updated default

Changed default from `"1"` to `"2"` so new setups default to the most common account type (MetaMask/Gnosis Safe).

### 3. `src/diagnose_config.py` — Improved diagnostics

- **Fixed** default `signature_type` from `"0"` to `"2"`
- **Fixed** RPC endpoint from broken `polygon-rpc.com` to `polygon-bor-rpc.publicnode.com`
- **Added** on-chain USDC balance check via Polygon JSON-RPC `eth_call` — checks both USDC native (`0x3c499c...`) and USDC.e bridged (`0x2791Bca...`) for both signer and funder addresses
- **Added** raw CLOB API response printing so auth errors and unexpected responses are visible
- **Added** balance diagnosis in summary section:
  - "Funds on-chain but not in CLOB" — suggests deposit needed or credentials mismatch
  - "No funds anywhere" — suggests wrong wallet or funds need to be bridged

### 4. `src/generate_api_key.py` — Fixed credential generation

- **Added** `POLYMARKET_SIGNATURE_TYPE` and `POLYMARKET_FUNDER` from env
- **Passes** them to `ClobClient` constructor so derived API credentials match the bot's configuration
- Previously created the client without these params, which could derive credentials for the wrong account type

### 5. `src/trading.py` — Improved `get_balance()` error visibility

- **Added** `DEBUG` log of raw API response before parsing
- **Added** `WARNING` when balance is $0 with the raw response (helps distinguish genuine $0 from misconfiguration)
- **Changed** exception log from generic "Error getting balance" to "Balance API call FAILED (returning 0.0 as fallback)"
- Still returns `0.0` on error (callers depend on this behavior)

### 6. `src/test_balance.py` — Fixed and improved

- **Replaced** `web3` dependency (not in `requirements.txt`) with `httpx` JSON-RPC `eth_call` for on-chain balance checks
- **Fixed** RPC endpoint from `polygon-rpc.com` to `polygon-bor-rpc.publicnode.com`
- **Fixed** default `signature_type` to `"2"`
- **Added** raw CLOB response printing
- **Added** checks for both signer and funder addresses across both USDC contracts

## Verification

```bash
# Confirm balance is visible
python -m src.test_balance
# Expected: CLOB BALANCE: $26.970754

# Run full diagnostics
python -m src.diagnose_config

# Ensure no test regressions
pytest tests/test_trading.py tests/test_arbitrage.py -v
# Expected: 40 passed
```

## Key Learnings

1. **`polygon-rpc.com` is unreliable** — it silently returns RPC errors that look like $0 balances. Use `polygon-bor-rpc.publicnode.com` or `1rpc.io/matic` instead.
2. **Polymarket's CLOB API returns $0 for wrong signature_type without any error** — this makes misconfiguration look like an empty account. Diagnostics must check multiple types and show raw responses.
3. **Most MetaMask users are `signature_type=2`** (Gnosis Safe), not `0` (EOA) or `1` (Magic Link proxy). The Polymarket profile API at `GET /public-profile?address=<addr>` returns the `proxyWallet` field to confirm the mapping.
4. **The `py-clob-client` derives the same API key regardless of `signature_type`** — the key is deterministic from the private key. The `signature_type` only affects which address the server queries when processing balance/order requests.
