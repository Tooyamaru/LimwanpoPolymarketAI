# PROJECT STATUS — Polymarket Quant Bot

**Last updated:** 2026-06-23  
**App version:** 0.10.0  
**Backend:** FastAPI + PostgreSQL + Redis  
**Active workflow:** Start application (port 5000)

---

## IMPORTANT: LimwanpoPolymarketAI Is A Polymarket Quant Bot

LimwanpoPolymarketAI is a Polymarket Quant Bot — a prediction-market engine, not a crypto trading bot.  
See **README.md** for full business-model details, audit assumptions, and architecture philosophy.

---

## Layer Status

| Layer | Name | Status | Interval |
|-------|------|--------|----------|
| 1 | Market Collector | ✅ COMPLETE | 5s |
| 2 | Scanner | ✅ COMPLETE | 300s |
| 3 | Universe Sync | ✅ COMPLETE | 60s |
| 3b | Price Refresh | ✅ COMPLETE | 10s |
| 4 | Signal Engine | ✅ COMPLETE | 10s |
| 5 | Opportunity Engine | ✅ COMPLETE | 30s |
| 6 | Strategy Engine | ✅ COMPLETE | 60s |
| 7 | Execution Engine | ✅ COMPLETE (paper) | 30s |
| 8 | Position Tracking | ✅ COMPLETE | 30s |
| **9** | **Risk Engine** | **✅ COMPLETE** | **15s** |
| **10** | **Portfolio Reporting** | **✅ COMPLETE** | — |
| 11 | Live Trading | ⬜ NEXT | — |
| 12 | Backtesting | ⬜ FUTURE | — |
| 13 | Alert System | ⬜ FUTURE | — |

---

## Layer 9 — Risk Engine (2026-06-23)

**Pipeline position:** Strategy Engine → **Risk Engine** → Execution Engine

**Files:**
- `models/risk_event.py` — `risk_events` table
- `repositories/risk_repository.py` — create / query / stats
- `services/risk_engine.py` — 5-rule evaluator
- `api/v1/risk.py` — `GET /risk`, `/risk/blocked`, `/risk/stats`

**Status lifecycle:**
```
PENDING → RISK_APPROVED → EXECUTED   (normal path)
PENDING → BLOCKED                    (risk rule tripped)
```

**5 Risk Rules:**
| Rule | Description |
|------|-------------|
| DUPLICATE_POSITION | Same condition_id already OPEN |
| MAX_OPEN_POSITIONS | Total open positions ≥ 10 |
| MAX_EXPOSURE | Open positions for this asset ≥ 3 |
| DAILY_LOSS | Sum unrealized PnL ≤ −50.0 |
| DAILY_TRADES | Orders placed today ≥ 20 |

**Settings:**
```
RISK_ENGINE_ENABLED=true       RISK_ENGINE_INTERVAL_SECONDS=15
MAX_OPEN_POSITIONS=10          MAX_EXPOSURE_PER_ASSET=3
MAX_DAILY_LOSS=-50.0           MAX_DAILY_TRADES=20
```

---

## Refactor Summary (2026-06-23)

| Concern | Before | After |
|---------|--------|-------|
| Repository layer | `services/*_repository.py` | `repositories/*_repository.py` |
| Background loops | inline in `main.py` (~280 lines) | `workers/engine_workers.py` |
| API response schemas | inline `class Foo(BaseModel):` in routers | `schemas/*.py` (one file per domain) |
| Import hygiene | `from app.services import X_repo` | `from app.repositories import X_repo` |

**schemas/ coverage (14 files, 2026-06-23 audit):**
`classifier`, `discovery`, `health`, `market`, `opportunity`, `order`, `position`, `price`, `risk`, `scanner`, `signal`, `source_validation`, `strategy`, `universe`

---

## Background Loops

| Loop | Interval | Gate |
|------|----------|------|
| CollectorScheduler | 5s | — |
| run_scanner_loop | 300s | — |
| run_universe_sync_loop | 60s | sets universe_ready |
| run_price_refresh_loop | 10s | universe_ready |
| run_signal_engine_loop | 10s | universe_ready |
| run_opportunity_engine_loop | 30s | universe_ready |
| run_strategy_engine_loop | 60s | universe_ready |
| **run_risk_engine_loop** | **15s** | universe_ready |
| run_execution_engine_loop | 30s | universe_ready |
| run_position_tracking_loop | 30s | universe_ready |

---

## API Endpoints (full)

| Endpoint | Layer |
|----------|-------|
| `GET /api/v1/health` | — |
| `GET /api/v1/health/detailed` | — |
| `GET /api/v1/markets` | L1 |
| `GET /api/v1/markets/active` | L1 |
| `GET /api/v1/markets/latest` | L1 |
| `GET /api/v1/discovery` | L2 |
| `POST /api/v1/discovery/run` | L2 |
| `GET /api/v1/discovery/markets` | L2 |
| `GET /api/v1/scanner` | L2 |
| `GET /api/v1/scanner/active` | L2 |
| `GET /api/v1/scanner/stats` | L2 |
| `GET /api/v1/classifier` | L2 |
| `GET /api/v1/classifier/updown` | L2 |
| `GET /api/v1/classifier/stats` | L2 |
| `GET /api/v1/source-validation` | L2 |
| `GET /api/v1/source-validation/search` | L2 |
| `GET /api/v1/source-validation/audit` | L2 |
| `POST /api/v1/source-validation/run` | L2 |
| `GET /api/v1/universe` | L3 |
| `GET /api/v1/universe/active` | L3 |
| `GET /api/v1/universe/upcoming` | L3 |
| `GET /api/v1/universe/stats` | L3 |
| `POST /api/v1/universe/sync` | L3 |
| `GET /api/v1/price/latest` | L3b |
| `GET /api/v1/price/active` | L3b |
| `GET /api/v1/price/stats` | L3b |
| `GET /api/v1/price/{condition_id}` | L3b |
| `GET /api/v1/signals/latest` | L4 |
| `GET /api/v1/signals/active` | L4 |
| `GET /api/v1/signals/stats` | L4 |
| `GET /api/v1/signals/{condition_id}` | L4 |
| `GET /api/v1/opportunities` | L5 |
| `GET /api/v1/opportunities/top` | L5 |
| `GET /api/v1/opportunities/stats` | L5 |
| `GET /api/v1/opportunities/{condition_id}` | L5 |
| `GET /api/v1/strategies` | L6 |
| `GET /api/v1/strategies/active` | L6 |
| `GET /api/v1/strategies/stats` | L6 |
| `GET /api/v1/risk` | L9 |
| `GET /api/v1/risk/blocked` | L9 |
| `GET /api/v1/risk/stats` | L9 |
| `GET /api/v1/orders` | L7 |
| `GET /api/v1/orders/stats` | L7 |
| `GET /api/v1/orders/open` | L7 |
| `GET /api/v1/orders/{id}` | L7 |
| `GET /api/v1/positions` | L8 |
| `GET /api/v1/positions/open` | L8 |
| `GET /api/v1/positions/stats` | L8 |
| `GET /api/v1/positions/{id}` | L8 |

---

## Known Limitations

1. Markets in AMM init phase (mid ≈ 0.50) — limited signal generation
2. Paper mode only — no real CLOB order submission
3. Quantity hardcoded to 1.0 per fill
4. No position close trigger (expiry-based close is passive via universe status)
5. No Alembic — schema managed by startup migrations
