# Polymarket 15min Arbitrage Bot

Professional arbitrage bot for cryptocurrency 15-minute markets on Polymarket.

> 🆕 **Multi-Market Support**: Now monitors BTC, ETH, SOL, BNB, DOGE, XRP 15min markets in parallel using asyncio.

## 🎯 Strategy

**Pure arbitrage**: Buy both sides (UP + DOWN) when total cost < $1.00 to guarantee profit regardless of outcome.

```
BTC goes up (UP):     $0.48
BTC goes down (DOWN): $0.51
─────────────────────────
Total:                $0.99  ✅ < $1.00
Profit:               $0.01 per share (1.01%)
```

**Why does it work?**
- At close, ONE of the two sides pays $1.00 per share
- If you paid $0.99 total, you earn $0.01 no matter which side wins
- It's **guaranteed profit** (pure arbitrage)

---

## 🚀 Quick Start

### 1. Clone and install:
```bash
git clone https://github.com/fernando-karl/Polymarket-trading-bot-15min-BTC
cd Polymarket-trading-bot-15min-BTC
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .\.venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure:
```bash
cp .env.example .env
# Edit .env with your private key and API credentials
```

### 3. Run:
```bash
# Single market (BTC)
python -m src.simple_arb_bot

# Multi-market (BTC, ETH, SOL in parallel) — RECOMMENDED
python -m src.multi_market_bot
```

---

## 📊 Running Modes

### Single Market Mode
```bash
python -m src.simple_arb_bot
```
Monitors BTC 15min market only.

### Multi-Market Mode (Recommended)
```bash
python -m src.multi_market_bot
```
Monitors **BTC, ETH, SOL** 15min markets in **parallel** using asyncio. Auto-detects active markets and switches when contracts close.

### WebSocket vs HTTP Polling

| Mode | Latency | Reliability |
|------|---------|-------------|
| `USE_WSS=true` | ~5ms per update | Higher (push) |
| `USE_WSS=false` | ~200ms per scan | Lower (poll) |

---

## 🔐 Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `POLYMARKET_PRIVATE_KEY` | Wallet private key (starts with `0x`) |
| `POLYMARKET_API_KEY` | API key from `python -m src.generate_api_key` |
| `POLYMARKET_API_SECRET` | API secret |
| `POLYMARKET_API_PASSPHRASE` | API passphrase |

### Trading
| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_PAIR_COST` | `0.991` | Max combined cost to trigger arbitrage |
| `ORDER_SIZE` | `5` | Shares per trade (minimum 5) |
| `ORDER_TYPE` | `FOK` | Order type: FOK, FAK, GTC |
| `DRY_RUN` | `true` | Simulation mode |
| `USE_WSS` | `true` | Enable WebSocket feed |
| `MULTI_MARKET_SLUGS` | auto | Comma-separated market slugs |

### Risk Management
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_DAILY_LOSS` | `20` | Max loss per day |
| `MAX_POSITION_SIZE` | `50` | Max position per trade |
| `MAX_TRADES_PER_DAY` | `50` | Max trades per day |
| `MIN_BALANCE_REQUIRED` | `10` | Minimum balance to trade |

---

## ⚡ Performance Optimizations

The bot includes several optimizations for low-latency arbitrage:

| Optimization | Impact |
|-------------|--------|
| **WSS Push Updates** | ~5ms vs 200ms polling |
| **Cache Warmup** | Eliminates ~300ms cold HTTP |
| **FOK No-Polling** | -500ms to -3000ms |
| **Dirty Flag Cache** | Reduces allocations in hot path |
| **Background Balance Refresh** | Never blocks on HTTP in hot path |
| **Shared Rate Limiter** | Coordinates with pm_bot (Rust) |

### Hot Path Latency (measured)
```
WSS push:          ~5ms
Check arbitrage:   ~1ms
Sign + Submit:     ~150ms (HTTP)
FOK verify:        ~0ms
───────────────────────────
Total:            ~156ms
```

---

## 🔄 Multi-Market Architecture

```
┌─────────────────────────────────────────┐
│         MultiMarketBot (asyncio)        │
├─────────────┬─────────────┬─────────────┤
│   BTC Bot   │   ETH Bot   │   SOL Bot   │
│   (WSS)     │   (WSS)     │   (WSS)     │
├─────────────┴─────────────┴─────────────┤
│      SharedRateLimiter (file lock)      │
└─────────────────────────────────────────┘
```

- Each market runs its own WSS connection
- asyncio manages all markets in parallel
- Shared rate limiter prevents 429 errors
- Auto-refreshes markets every 60 seconds

---

## 📁 Project Structure

```
Polymarket-trading-bot-15min-BTC/
├── src/
│   ├── simple_arb_bot.py       # Single-market arbitrage bot
│   ├── multi_market_bot.py     # Multi-market bot (asyncio)
│   ├── config.py               # Configuration loader
│   ├── trading.py              # Order execution + rate limiter
│   ├── shared_rate_limiter.py  # Shared API rate limiter
│   ├── wss_market.py          # WebSocket client with dirty-flag cache
│   ├── lookup.py              # Market slug discovery
│   ├── risk_manager.py        # Risk controls
│   ├── statistics.py          # Trade tracking
│   └── ...
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🛠️ Utilities

```bash
# Generate API credentials
python -m src.generate_api_key

# Test wallet balance
python -m src.test_balance

# Diagnose configuration issues
python -m src.diagnose_config
```

---

## ⚠️ Warnings

- ⚠️ **Start with DRY_RUN=true**
- ⚠️ Markets close every **15 minutes** — don't accumulate positions
- ⚠️ Spread arb only works when UP + DOWN < threshold (rare windows)
- ⚠️ This software is **educational** — use at your own risk

---

## 📈 Example Output

```
🚀 Starting Multi-Market Arbitrage Bot
📊 Markets: btc-updown-15m-xxx, eth-updown-15m-xxx, sol-updown-15m-xxx
🔖 Mode: 🔸 SIMULATION
🎯 Threshold: $0.991
============================================================

[WSS Eval #1] 13:05:29
No arb: $1.0100 worst=$1.0100 vwap=$1.0100 gap=$-0.0190 [9m 31s]

🎯 ARBITRAGE OPPORTUNITY
 UP: $0.4950
 DOWN: $0.4950
 Total: $0.9900
 Profit: $0.0100 (1.01%)
✅ ARBITRAGE EXECUTED (AMBOS OS LEGS FILLED)
```

---

## 🔗 Resources

- [Polymarket](https://polymarket.com/)
- [BTC 15min Markets](https://polymarket.com/crypto/15M)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)

---

## ⚖️ Disclaimer

This software is for educational purposes only. Trading involves risk. Use at your own risk.
