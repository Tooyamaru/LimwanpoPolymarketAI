# Polymarket Quant Bot

Production-grade quantitative trading infrastructure for Polymarket prediction markets,
with data feeds from Binance Spot and Chainlink price oracles.

---

## Project Structure

```
polymarket-quant-bot/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py            # Router registry
│   │   │       ├── health.py              # GET /api/v1/health (+ /detailed)
│   │   │       ├── markets.py             # GET /api/v1/markets/*
│   │   │       ├── discovery.py           # GET /api/v1/discovery/*
│   │   │       └── scanner.py             # GET /api/v1/scanner/*
│   │   ├── collector/
│   │   │   ├── binance_spot.py            # Binance Spot ticker collector
│   │   │   ├── binance_futures.py         # Placeholder (Sprint 4)
│   │   │   ├── polymarket.py              # Polymarket CLOB price collector
│   │   │   ├── chainlink.py               # Placeholder (Sprint 4)
│   │   │   └── scheduler.py              # 5-second price collection loop
│   │   ├── core/
│   │   │   ├── database.py                # SQLAlchemy async engine (lazy init)
│   │   │   ├── logging.py                # structlog JSON logging
│   │   │   └── redis.py                  # Async Redis connection pool
│   │   ├── models/
│   │   │   ├── market.py                  # Market ORM model
│   │   │   ├── market_snapshot.py         # MarketSnapshot ORM model
│   │   │   ├── scanner_market.py          # ScannerMarket ORM model
│   │   │   └── discovery_run.py           # DiscoveryRun diagnostics model
│   │   ├── services/
│   │   │   ├── market_repository.py       # Market persistence layer
│   │   │   ├── market_discovery.py        # Full market discovery engine
│   │   │   ├── scanner.py                 # Scanner orchestrator
│   │   │   └── scanner_repository.py      # Scanner persistence layer
│   │   ├── config/
│   │   │   └── settings.py                # Pydantic Settings
│   │   ├── tests/
│   │   │   ├── conftest.py
│   │   │   ├── test_health.py
│   │   │   ├── test_binance_collector.py
│   │   │   ├── test_market_repository.py
│   │   │   ├── test_market_discovery.py   # Sprint 3
│   │   │   ├── test_scanner_repository.py # Sprint 3
│   │   │   └── test_scanner.py            # Sprint 3
│   │   └── main.py                        # FastAPI factory + dual scheduler
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   └── pyproject.toml
│
├── frontend/                              # Sprint 5+
│
├── database/
│   ├── init/01_extensions.sql
│   └── migrations/                        # Alembic (Sprint 4)
│
├── deployment/
│   └── docker-compose.prod.yml
│
├── docs/architecture.md
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Sprint 3 Architecture — Discovery & Scanner Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                              │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │   Price Collector  (every 5 s)                                 │    │
│  │   Binance Spot → Polymarket prices → PostgreSQL snapshots      │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │   Market Scanner   (every 300 s + on startup)                  │    │
│  │                                                                 │    │
│  │   MarketDiscoveryService                                        │    │
│  │     Paginate ALL Polymarket markets (~30k+)                    │    │
│  │     Match: asset ∈ {BTC,ETH,SOL,XRP}                          │    │
│  │            timeframe ∈ {5m,15m,1H}                            │    │
│  │     Record WHY each market matched (transparency)              │    │
│  │         raw_title, matching_rule, detected_asset,              │    │
│  │         detected_timeframe                                      │    │
│  │          │                                                      │    │
│  │   ScannerService                                                │    │
│  │     Upsert → scanner_markets table                             │    │
│  │     Mark stale markets that left the active set                │    │
│  │     Persist → discovery_runs table (diagnostics)               │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  REST API                                                               │
│    GET /api/v1/health              Basic health + uptime               │
│    GET /api/v1/health/detailed     DB + Redis status                   │
│    GET /api/v1/markets             All markets (price universe)        │
│    GET /api/v1/markets/active      Active markets                      │
│    GET /api/v1/markets/latest      Latest price snapshots              │
│    GET /api/v1/discovery           Latest discovery run stats          │
│    POST /api/v1/discovery/run      Trigger on-demand discovery scan    │
│    GET /api/v1/discovery/markets   All matched markets + transparency  │
│    GET /api/v1/scanner             Full scanner universe               │
│    GET /api/v1/scanner/active      Active scanner markets              │
│    GET /api/v1/scanner/stats       Aggregate stats by asset/status     │
└─────────────────────────────────────────────────────────────────────────┘
            │
     PostgreSQL tables
       markets
       market_snapshots
       scanner_markets      ← Sprint 3 (universe + transparency)
       discovery_runs       ← Sprint 3 (per-run diagnostics)
```

### Discovery Matching Rules

Asset rules (first match wins, case-insensitive):

| Rule Name      | Pattern         | Normalised |
|----------------|-----------------|------------|
| `exact_BTC`    | `\bBTC\b`       | BTC        |
| `exact_ETH`    | `\bETH\b`       | ETH        |
| `exact_SOL`    | `\bSOL\b`       | SOL        |
| `exact_XRP`    | `\bXRP\b`       | XRP        |
| `word_Bitcoin` | `\bBitcoin\b`   | BTC        |
| `word_Ethereum`| `\bEthereum\b`  | ETH        |
| `word_Solana`  | `\bSolana\b`    | SOL        |
| `word_Ripple`  | `\bRipple\b`    | XRP        |

Timeframe rules:

| Rule Name    | Pattern                     | Normalised |
|--------------|-----------------------------|------------|
| `tf_5m`      | `5 min(ute)?s?`             | 5m         |
| `tf_15m`     | `15 min(ute)?s?`            | 15m        |
| `tf_1H_abbr` | `1H` / `1h`                 | 1H         |
| `tf_1H_word` | `1 hour` / `1-hour`         | 1H         |
| `tf_60m`     | `60 min(ute)?s?`            | 1H         |

Every matched market stores `matching_rule = "<asset_rule> + <tf_rule>"` for full auditability.

---

## All Sprints

### Sprint 1 ✅ — Infrastructure
FastAPI, Docker, PostgreSQL, Redis, health endpoint, project structure.

### Sprint 2 ✅ — Data Collection Layer
Binance Spot collector, Polymarket price collector, ORM models (`markets`, `market_snapshots`), 5-second scheduler, price API endpoints.

### Sprint 3 ✅ — Discovery & Scanner Layer
Full market discovery engine (paginates all 30k+ Polymarket markets), scanner universe builder, transparency metadata for every matched market, `scanner_markets` + `discovery_runs` tables, discovery and scanner API endpoints.

### Sprint 4 — Planned
Binance Futures + Chainlink collectors, Alembic migrations.

### Sprint 5 — Planned
Analysis services.

---

## Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Runtime     | Python 3.12                       |
| API         | FastAPI + Uvicorn                 |
| Database    | PostgreSQL 16 + SQLAlchemy 2.0    |
| Cache / Bus | Redis 7                           |
| Containers  | Docker + Docker Compose           |
| Logging     | structlog (JSON)                  |
| Config      | pydantic-settings                 |
| Testing     | pytest + anyio + aiosqlite        |

---

## Quick Start

```bash
# 1. Copy env
cp .env.example .env

# 2. Start all services
docker-compose up --build

# 3. Verify
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/discovery
curl http://localhost:8000/api/v1/scanner/stats
curl http://localhost:8000/api/v1/scanner/active
```

---

## Full API Reference

| Method | Path                        | Description                                         |
|--------|-----------------------------|-----------------------------------------------------|
| GET    | `/api/v1/health`            | Status, version, uptime                             |
| GET    | `/api/v1/health/detailed`   | DB + Redis dependency health                        |
| GET    | `/api/v1/markets`           | All tracked markets                                 |
| GET    | `/api/v1/markets/active`    | Active markets only                                 |
| GET    | `/api/v1/markets/latest`    | Latest price snapshots                              |
| GET    | `/api/v1/discovery`         | Latest discovery run diagnostics                    |
| POST   | `/api/v1/discovery/run`     | Trigger on-demand full market discovery             |
| GET    | `/api/v1/discovery/markets` | All matched markets with transparency metadata      |
| GET    | `/api/v1/scanner`           | Full scanner market universe                        |
| GET    | `/api/v1/scanner/active`    | Active scanner markets                              |
| GET    | `/api/v1/scanner/stats`     | Aggregate stats by asset and health status          |
| GET    | `/api/docs`                 | Swagger UI                                          |

### Discovery response (Sprint 3)

```json
{
  "run_at": "2026-06-18T05:30:00Z",
  "total_markets_scanned": 30000,
  "matched_markets": 42,
  "btc": 18,
  "eth": 12,
  "sol": 8,
  "xrp": 4
}
```

### Scanner market response (Sprint 3)

```json
{
  "id": 1,
  "asset": "BTC",
  "timeframe": "5m",
  "market_id": "0xabc...",
  "health_status": "active",
  "created_at": "2026-06-18T05:00:00Z",
  "raw_title": "Will BTC be above $70k in 5m?",
  "matching_rule": "exact_BTC + tf_5m",
  "detected_asset": "BTC",
  "detected_timeframe": "5m"
}
```

### Scanner stats response

```json
{
  "total": 42,
  "active": 38,
  "stale": 4,
  "by_asset": {
    "BTC": 18,
    "ETH": 12,
    "SOL": 8,
    "XRP": 4
  }
}
```

---

## Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

**Sprint 3 target: 43 tests passed**

Test modules:
- `test_health.py`              — health endpoint schema + status codes
- `test_binance_collector.py`   — collector with mock HTTP transport
- `test_market_repository.py`   — repository against in-memory SQLite
- `test_market_discovery.py`    — discovery matching logic + mock HTTP
- `test_scanner_repository.py`  — scanner CRUD + stale marking + stats
- `test_scanner.py`             — scanner orchestration end-to-end

---

## Environment Variables

| Variable                    | Default     | Description                               |
|-----------------------------|-------------|-------------------------------------------|
| `DATABASE_URL`              | *(asyncpg)* | PostgreSQL DSN                            |
| `REDIS_URL`                 | `redis://…` | Redis DSN                                 |
| `APP_ENV`                   | `development` | Environment name                        |
| `LOG_LEVEL`                 | `INFO`      | Log verbosity                             |
| `COLLECTOR_INTERVAL_SECONDS`| `5`         | Price collection frequency                |
| `COLLECTOR_ENABLED`         | `true`      | Enable/disable price collector            |
| `SCANNER_INTERVAL_SECONDS`  | `300`       | Market universe refresh frequency         |
| `SCANNER_ENABLED`           | `true`      | Enable/disable market scanner             |
| `SCANNER_RUN_ON_STARTUP`    | `true`      | Run scanner once immediately at boot      |

---

## Docker Commands

```bash
docker-compose up --build          # Start (dev, hot-reload)
docker-compose up -d --build       # Start in background
docker-compose down                # Stop
docker-compose down -v             # Full reset
docker-compose logs -f backend     # Backend logs
docker-compose exec backend bash   # Shell access
docker-compose exec postgres psql -U postgres -d polymarket
```
