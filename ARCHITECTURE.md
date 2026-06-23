# ARCHITECTURE — Polymarket Quant Bot

## Overview

Production-grade quantitative trading infrastructure for Polymarket prediction markets.
Integrates live price feeds (Binance + Polymarket CLOB) and executes paper trades through a
9-layer pipeline with full risk gating.

---

## Folder Structure

```
backend/app/
├── api/            # FastAPI routers (HTTP boundary only — no business logic)
│   └── v1/         # /api/v1/* endpoints (one file per domain)
├── collector/      # External data ingestion (Binance Spot, Polymarket CLOB pages)
├── config/         # Settings via pydantic-settings (env + .env file)
├── core/           # Cross-cutting infrastructure (database, redis, logging)
├── models/         # SQLAlchemy ORM models (1:1 mapping to DB tables)
├── repositories/   # DB persistence layer (all SQL queries)
├── schemas/        # Pydantic request/response schemas (API boundary)
├── services/       # Business logic engines (Signal, Opportunity, Strategy…)
├── utils/          # Shared pure-function helpers
├── workers/        # Long-running async background loops
│   └── engine_workers.py
└── tests/          # pytest test suite
```

---

## Layer Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  EXTERNAL SOURCES                                                │
│  Binance Spot API   Polymarket CLOB API   Gamma Events API       │
└──────────┬──────────────────┬─────────────────────┬─────────────┘
           │                  │                      │
           ▼                  ▼                      ▼
┌──────────────────┐  ┌───────────────┐  ┌──────────────────────┐
│ Layer 1 Collector│  │ Layer 2 Scanner│  │ Layer 3 Universe Sync│
│ (market + price) │  │ (20k markets) │  │ (12 known series)    │
└────────┬─────────┘  └───────────────┘  └──────────┬───────────┘
         │                                           │
         ▼                                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3b  Price Refresh  (CLOB bid/ask for 12 active markets)   │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4  Signal Engine  (price delta, spread, seed deviation)   │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5  Opportunity Engine  (composite score 0–100)            │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 6  Strategy Engine  (score threshold → OPEN_LONG_YES/NO)  │
│  ➜ emits TradeDecision with status=PENDING                      │
└────────────────────────────────────┬────────────────────────────┘
                                     │ (PENDING decisions)
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 9  Risk Engine  (5 portfolio risk rules)                  │
│  ➜ PENDING → RISK_APPROVED  or  PENDING → BLOCKED               │
│  ➜ persists RiskEvent (ALLOW/BLOCK + reason + portfolio state)  │
└────────────────────────────────────┬────────────────────────────┘
                                     │ (RISK_APPROVED decisions only)
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 7  Execution Engine  (paper-mode fill, instant, no slip)  │
│  ➜ Order (FILLED), TradeDecision status → EXECUTED              │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 8  Position Tracking  (create from fill, refresh PnL)     │
│  ➜ Position (OPEN), unrealized_pnl updated every 30 s          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dependency Diagram

```
api/v1/*.py
  └─ depends on ─► repositories/*.py  ─► models/*.py ─► core/database.py
  └─ returns ───► schemas/*.py

services/*_engine.py
  └─ depends on ─► repositories/*.py
  └─ depends on ─► services/clob_client.py

workers/engine_workers.py
  └─ manages ────► services/*_engine.py (via session factory)
  └─ depends on ─► config/settings.py
  └─ reports to ─► main.py (asyncio tasks)

collector/scheduler.py
  └─ depends on ─► repositories/market_repository.py
  └─ depends on ─► collector/binance_spot.py
  └─ depends on ─► collector/polymarket.py
```

---

## Request Flow (API)

```
HTTP GET /api/v1/opportunities
  → FastAPI router (api/v1/opportunities.py)
    → Depends(get_db_session)         [core/database.py]
    → opportunity_repository.get_all_opportunities(session)  [repositories/]
      → SELECT * FROM opportunities ORDER BY score DESC
    → [OpportunityResponse.model_validate(row) for row in rows]   [schemas/]
  → JSON response
```

---

## Data Flow (Pipeline)

```
Binance API ──► collector/binance_spot.py
                  └── save_market() ──► markets table

Polymarket CLOB ──► collector/polymarket.py
                      └── save_market() ──► markets table

Gamma Events API ──► services/market_universe_service.py
                       └── upsert_universe_market() ──► market_universe table

CLOB bid/ask ──► services/market_price_service.py
                   └── save_snapshot() ──► market_price_snapshots table

Signal Engine ──► services/signal_engine.py
                    └── save_signal() ──► signals table

Opportunity Engine ──► services/opportunity_engine.py
                         └── upsert_opportunity() ──► opportunities table

Strategy Engine ──► services/strategy_engine.py
                      └── insert_decision() ──► trade_decisions (PENDING)

Risk Engine ──► services/risk_engine.py
                  ├── create_risk_event() ──► risk_events table
                  └── update td.status ──► trade_decisions (RISK_APPROVED | BLOCKED)

Execution Engine ──► services/execution_engine.py
                       ├── create_order() ──► orders table (FILLED)
                       └── update td.status ──► trade_decisions (EXECUTED)

Position Service ──► services/position_service.py
                       └── create_position() ──► positions table (OPEN)
                       └── update pnl ──► positions table (unrealized_pnl)
```

---

## Worker Flow

All workers run as `asyncio.Task` objects, started in `main.py` lifespan.

```
main.py lifespan
├── CollectorScheduler.run()          interval=5s    (always enabled)
├── run_scanner_loop()                interval=300s  (SCANNER_ENABLED)
├── run_universe_sync_loop()          interval=60s   (UNIVERSE_SYNC_ENABLED)
│     └── sets universe_ready_event after first sync
├── run_price_refresh_loop()          interval=10s   (PRICE_REFRESH_ENABLED)
│     └── waits on universe_ready_event
├── run_signal_engine_loop()          interval=10s   (SIGNAL_ENGINE_ENABLED)
│     └── waits on universe_ready_event
├── run_opportunity_engine_loop()     interval=30s   (OPPORTUNITY_ENGINE_ENABLED)
│     └── waits on universe_ready_event
├── run_strategy_engine_loop()        interval=60s   (STRATEGY_ENGINE_ENABLED)
│     └── waits on universe_ready_event
├── run_risk_engine_loop()            interval=15s   (RISK_ENGINE_ENABLED)
│     └── waits on universe_ready_event
├── run_execution_engine_loop()       interval=30s   (EXECUTION_ENGINE_ENABLED)
│     └── waits on universe_ready_event
└── run_position_tracking_loop()      interval=30s   (always enabled)
      └── waits on universe_ready_event
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 |
| Web Framework | FastAPI + Uvicorn (async) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Database | PostgreSQL (Replit managed) |
| Cache / Health | Redis 7 |
| Settings | pydantic-settings |
| Logging | structlog (JSON output) |
| HTTP Client | httpx (async) |
| Background Jobs | asyncio.Task (no Celery) |
