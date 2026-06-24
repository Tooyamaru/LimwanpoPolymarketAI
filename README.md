# Polymarket Quant Bot

Production-grade quantitative trading infrastructure for Polymarket prediction markets.
Integrates live price feeds from Binance and Polymarket CLOB to analyze, score, screen, and
paper-trade "Up-or-Down" binary outcome markets for BTC, ETH, SOL, and XRP.

**Version:** 0.10.0 — Layers 1–10 complete, Layer 11 (Live Trading) next.

---

## IMPORTANT: LimwanpoPolymarketAI Is A Polymarket Quant Bot

### Project Identity

**Official name:** LimwanpoPolymarketAI  
**Project type:** Polymarket Quant Bot — Prediction Market Intelligence System — Probability-Based Decision Engine

This project is **NOT** a Binance Trading Bot, Spot Trading Bot, Futures Trading Bot, Arbitrage Bot, Market Making Bot, Copy Trading Bot, or Traditional Crypto Trading System.

### Business Model

LimwanpoPolymarketAI is a prediction-market system. The system:

1. Collects market data and price feeds.
2. Analyzes quantitative signals.
3. Estimates outcome probabilities.
4. Determines whether YES or NO has statistical edge.
5. Executes YES or NO contracts on Polymarket.
6. Manages portfolio exposure.
7. Takes profit when opportunities exist.

**The system predicts outcomes. The system does NOT trade cryptocurrencies directly.**

### Traded Instruments

| Instrument | Role |
|---|---|
| YES contracts on Polymarket | ✅ Actual traded instrument |
| NO contracts on Polymarket | ✅ Actual traded instrument |
| BTC | ❌ Prediction target only — never bought or sold directly |
| ETH | ❌ Prediction target only — never bought or sold directly |
| SOL | ❌ Prediction target only — never bought or sold directly |
| XRP | ❌ Prediction target only — never bought or sold directly |

### Role of External Data Sources

Binance, Chainlink, and all external market/price feeds are used **exclusively** as signal inputs, prediction inputs, probability features, and market intelligence sources. They are **not** execution venues. They are **not** traded assets. The only execution venue is **Polymarket**.

### Primary Target Markets

- BTC Up / Down (binary Polymarket prediction markets)
- ETH Up / Down (binary Polymarket prediction markets)
- SOL Up / Down (binary Polymarket prediction markets)
- XRP Up / Down (binary Polymarket prediction markets)

These are prediction markets — not spot assets, not futures contracts, not perpetual contracts.

### Quant Philosophy — Probabilistic Edge

LimwanpoPolymarketAI is a **Quant Bot**, not a directional signal bot.

The goal is NOT: *"Predict if BTC goes up."*  
The goal IS: *"Detect probability mispricing."*

The objective is to identify **pricing inefficiencies** between:

- **(A)** The probability implied by current Polymarket market prices
- **(B)** The probability estimated by LimwanpoPolymarketAI internal models

The system evaluates both directions of mispricing:

**Example 1 — Market underprices YES (BUY YES opportunity):**

```
Market YES implied probability:   40%
Model estimated probability:      68%
Edge:                            +28%  →  BUY YES
```

**Example 2 — Market overprices YES (BUY NO opportunity):**

```
Market YES implied probability:   95%
Model estimated probability:      80%
Edge:                            -15%  →  BUY NO
```

In Example 2, even though the model agrees the event is *likely* (80%), buying YES is still a **bad trade** — because the market has already priced in 95%. The model believes YES is *less likely* than the market implies, creating an edge on the NO side.

**The system does NOT operate on simple directional logic such as:**

> "BTC going up → BUY YES"  
> "BTC going down → BUY NO"

That is a directional price-movement bot. LimwanpoPolymarketAI is a **probability mispricing engine** — it searches for markets where Polymarket's implied probability diverges meaningfully from the model's estimated true probability. The underlying asset direction is one input into that probability estimate, not the sole decision criterion.

### Position & Exposure Philosophy

**Exposure Management > Position Count**

- Multiple entries on the same market are valid.
- Multiple positions on the same `condition_id` are valid if exposure rules permit.
- Duplicate entries must NOT be automatically classified as bugs.
- A finding must verify violation of an explicit exposure rule before being classified as a duplicate defect.

### Profit-Taking Philosophy

Profit-taking before market settlement is **valid and expected**:

```
Open Position → Opportunity exists → Take profit → Close position
```

The system does not require waiting until event resolution or market expiry. Audits must not classify early profit-taking as a defect.

### Audit Assumptions

Before reporting a bug, determine whether the finding comes from:

- **(A) Prediction-market logic** — valid basis for a finding
- **(B) Traditional spot/futures-trading assumptions** — invalid basis unless also applicable to prediction markets

The following assumptions are **invalid** for LimwanpoPolymarketAI:
- One market = one position
- Must hold until expiry
- Must hold until settlement
- Early profit-taking is wrong
- Multiple entries are automatically bugs

---

## Architecture

```
FastAPI (async) + SQLAlchemy 2.0 (asyncpg → PostgreSQL) + Redis
httpx (async CLOB/Gamma API) + structlog (JSON logging) + pydantic-settings
```

Full architecture diagram: [ARCHITECTURE.md](ARCHITECTURE.md)  
Full database schema: [DATABASE.md](DATABASE.md)

---

## Layer Pipeline

```
Layer 1  Collector        Binance Spot + Polymarket prices every 5s
Layer 2  Scanner          Full Polymarket scan (~250k markets every 5m)
Layer 3  Universe Sync    12 known "Up-or-Down" series tracked via Gamma API
Layer 3b Price Refresh    CLOB bid/ask for all active universe markets every 10s
Layer 4  Signal Engine    Detect price move, spread compression, seed deviation
Layer 5  Opportunity      Composite score (0–100) per active market every 30s
Layer 6  Strategy         Score threshold → OPEN_LONG_YES/NO trade decisions
Layer 9  Risk Engine  ★   5 portfolio rules → PENDING → RISK_APPROVED | BLOCKED
Layer 7  Execution        Paper-mode fills on RISK_APPROVED decisions every 30s
Layer 8  Position         Live PnL tracking on all open positions every 30s
```

---

## Project Structure

```
backend/app/
├── api/v1/         HTTP routers (no business logic, no inline schemas)
│   ├── health.py, markets.py, discovery.py, scanner.py, classifier.py
│   ├── universe.py, price.py, signals.py, opportunities.py
│   ├── strategies.py, risk.py, orders.py, positions.py
│   ├── source_validation.py
│   └── __init__.py
├── collector/      External data ingestion (Binance, Polymarket pages)
├── config/         pydantic-settings (env + .env)
├── core/           database.py, redis.py, logging.py
├── models/         SQLAlchemy ORM models (10 tables)
├── repositories/   All SQL queries (one file per domain)
├── schemas/        Pydantic response schemas (one file per domain, 14 files)
├── services/       Business logic engines
├── utils/          Shared pure-function helpers
├── workers/        Long-running async background loops
│   └── engine_workers.py
└── tests/          pytest suite
```

---

## Setup

```bash
# Start Redis
redis-server --daemonize yes --port 6379

# Start API
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

On Replit: use the **Start application** workflow.

---

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://…` | PostgreSQL DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `RISK_ENGINE_ENABLED` | `true` | Layer 9 risk gating |
| `MAX_OPEN_POSITIONS` | `10` | Max concurrent open positions |
| `MAX_EXPOSURE_PER_ASSET` | `3` | Max positions per asset (BTC/ETH/SOL/XRP) |
| `MAX_DAILY_LOSS` | `-50.0` | Daily loss limit (unrealized PnL, USD equiv) |
| `MAX_DAILY_TRADES` | `20` | Max paper fills per day |
| `EXECUTION_PAPER_MODE` | `true` | Paper mode (no real orders) |
| `UNIVERSE_SYNC_RUN_ON_STARTUP` | `true` | Overridden to `false` in Replit env |
| `PRICE_REFRESH_RUN_ON_STARTUP` | `true` | Overridden to `false` in Replit env |

---

## API Reference

Base prefix: `/api/v1`  
Swagger UI: `GET /api/docs`

| Layer | Method | Path | Description |
|-------|--------|------|-------------|
| — | GET | `/health` | Version + uptime |
| — | GET | `/health/detailed` | DB + Redis health |
| L1 | GET | `/markets` | All collected markets |
| L1 | GET | `/markets/active` | Active markets only |
| L1 | GET | `/markets/latest` | Latest price snapshots |
| L2 | GET | `/scanner` | Full scanner universe |
| L2 | GET | `/scanner/active` | Active scanner markets |
| L2 | GET | `/scanner/stats` | Asset/status breakdown |
| L2 | GET | `/discovery` | Latest discovery run stats |
| L2 | POST | `/discovery/run` | Trigger on-demand scan |
| L2 | GET | `/discovery/markets` | All matched markets with rule metadata |
| L2 | GET | `/classifier` | All classified markets |
| L2 | GET | `/classifier/updown` | UPDOWN markets only |
| L2 | GET | `/classifier/stats` | Classification breakdown |
| L2 | GET | `/source-validation` | Source diagnostics |
| L2 | GET | `/source-validation/search` | Free-text market search |
| L2 | GET | `/source-validation/audit` | All Up/Down candidates |
| L2 | POST | `/source-validation/run` | Full validation scan |
| L3 | GET | `/universe` | All universe markets |
| L3 | GET | `/universe/active` | Active markets |
| L3 | GET | `/universe/upcoming` | Upcoming markets |
| L3 | GET | `/universe/stats` | Asset × timeframe × status counts |
| L3 | POST | `/universe/sync` | Trigger immediate sync |
| L3b | GET | `/price/latest` | Most recent N snapshots |
| L3b | GET | `/price/active` | Latest snapshot per active market |
| L3b | GET | `/price/stats` | Snapshot count + coverage |
| L3b | GET | `/price/{condition_id}` | Snapshots for one market |
| L4 | GET | `/signals/latest` | Most recent signals |
| L4 | GET | `/signals/active` | Signals for active markets |
| L4 | GET | `/signals/stats` | Signal counts by type/severity |
| L4 | GET | `/signals/{condition_id}` | Signals for one market |
| L5 | GET | `/opportunities` | All markets with scores |
| L5 | GET | `/opportunities/top` | Top N by score |
| L5 | GET | `/opportunities/stats` | Direction + score aggregate |
| L5 | GET | `/opportunities/{condition_id}` | One market detail |
| L6 | GET | `/strategies` | All trade decisions |
| L6 | GET | `/strategies/active` | PENDING OPEN_LONG_* decisions |
| L6 | GET | `/strategies/stats` | Decision count + type breakdown |
| **L9** | **GET** | **`/risk`** | **All risk evaluation events** |
| **L9** | **GET** | **`/risk/blocked`** | **BLOCKED decisions** |
| **L9** | **GET** | **`/risk/stats`** | **Block rate + reason breakdown** |
| L7 | GET | `/orders` | All paper fills |
| L7 | GET | `/orders/open` | Open orders |
| L7 | GET | `/orders/stats` | Fill counts + avg prices |
| L7 | GET | `/orders/{id}` | Single order detail |
| L8 | GET | `/positions` | All positions |
| L8 | GET | `/positions/open` | Open positions with live PnL |
| L8 | GET | `/positions/stats` | PnL aggregate |
| L8 | GET | `/positions/{id}` | Single position detail |

---

## Background Workers

| Worker | Interval | Gate |
|--------|----------|------|
| CollectorScheduler | 5s | — |
| run_scanner_loop | 300s | — |
| run_universe_sync_loop | 60s | sets `universe_ready` |
| run_price_refresh_loop | 10s | `universe_ready` |
| run_signal_engine_loop | 10s | `universe_ready` |
| run_opportunity_engine_loop | 30s | `universe_ready` |
| run_strategy_engine_loop | 60s | `universe_ready` |
| **run_risk_engine_loop** | **15s** | `universe_ready` |
| run_execution_engine_loop | 30s | `universe_ready` |
| run_position_tracking_loop | 30s | `universe_ready` |

---

## Risk Engine Rules (Layer 9)

Decisions flow: **PENDING → Risk Engine → RISK_APPROVED → Execution** (or BLOCKED)

| Rule | Check | Setting |
|------|-------|---------|
| DUPLICATE_POSITION | OPEN position for same condition_id exists | — |
| MAX_OPEN_POSITIONS | Total OPEN positions ≥ limit | `MAX_OPEN_POSITIONS=10` |
| MAX_EXPOSURE | OPEN positions for this asset ≥ limit | `MAX_EXPOSURE_PER_ASSET=3` |
| DAILY_LOSS | Sum of unrealized PnL today ≤ limit | `MAX_DAILY_LOSS=-50.0` |
| DAILY_TRADES | Orders placed today ≥ limit | `MAX_DAILY_TRADES=20` |

---

## Event Classifier Rules

Priority: **UPDOWN > PRICE_RANGE > NEWS_EVENT > POLITICS > OTHER**

UPDOWN patterns: `up or down`, `down or up`, `up/down`, `up-or-down`, `updown`

---

## Tests

```bash
cd backend && pytest
```

---

## Current Progress

```
Layer 1  ✅ Market Collector
Layer 2  ✅ Scanner
Layer 3  ✅ Universe Sync + Price Refresh
Layer 4  ✅ Signal Engine
Layer 5  ✅ Opportunity Engine
Layer 6  ✅ Strategy Engine
Layer 7  ✅ Execution Engine (Paper Mode)
Layer 8  ✅ Position Tracking
Layer 9  ✅ Risk Engine
Layer 10 ✅ Portfolio Reporting (COMPLETE)
Layer 11 ⬜ Live Trading (next)
```

Roadmap: [ROADMAP_NEXT_PHASE.md](ROADMAP_NEXT_PHASE.md)
