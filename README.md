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
│   │   │       ├── __init__.py          # Router registry
│   │   │       ├── health.py            # GET /api/v1/health (+ /detailed)
│   │   │       └── markets.py           # GET /api/v1/markets/*
│   │   ├── collector/
│   │   │   ├── __init__.py
│   │   │   ├── binance_spot.py          # Binance Spot ticker collector
│   │   │   ├── binance_futures.py       # Placeholder (Sprint 3)
│   │   │   ├── polymarket.py            # Polymarket CLOB market collector
│   │   │   ├── chainlink.py             # Placeholder (Sprint 3)
│   │   │   └── scheduler.py            # Async 5-second collection loop
│   │   ├── core/
│   │   │   ├── database.py              # SQLAlchemy async engine (lazy init)
│   │   │   ├── logging.py              # structlog JSON logging
│   │   │   └── redis.py                # Async Redis connection pool
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── market.py               # Market ORM model
│   │   │   └── market_snapshot.py      # MarketSnapshot ORM model
│   │   ├── services/
│   │   │   └── market_repository.py    # DB persistence layer
│   │   ├── config/
│   │   │   └── settings.py             # Pydantic Settings management
│   │   ├── tests/
│   │   │   ├── conftest.py
│   │   │   ├── test_health.py          # Health endpoint tests
│   │   │   ├── test_binance_collector.py # Binance collector unit tests
│   │   │   └── test_market_repository.py # Repository integration tests
│   │   └── main.py                     # FastAPI factory + lifespan + scheduler
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   └── pyproject.toml
│
├── frontend/                            # Sprint 3+
│
├── database/
│   ├── init/
│   │   └── 01_extensions.sql           # PostgreSQL extensions
│   └── migrations/                     # Alembic migrations (Sprint 3)
│
├── deployment/
│   └── docker-compose.prod.yml         # Production Docker overrides
│
├── docs/
│   └── architecture.md                 # System architecture
│
├── docker-compose.yml                  # Development Docker Compose
├── .env.example                        # Environment variable template
├── .gitignore
└── README.md
```

---

## Sprint 2 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  CollectorScheduler (every 5 s)          │    │
│  │                                                         │    │
│  │   BinanceSpotCollector ──► BinanceSpotData[]            │    │
│  │          │                                              │    │
│  │   PolymarketCollector  ──► PolymarketMarketData[]       │    │
│  │          │                                              │    │
│  │   market_repository    ──► PostgreSQL                   │    │
│  │     save_market()           markets table               │    │
│  │     save_snapshot()         market_snapshots table      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  REST API                                                        │
│    GET /api/v1/health           Basic health + uptime            │
│    GET /api/v1/health/detailed  DB + Redis status                │
│    GET /api/v1/markets          All markets                      │
│    GET /api/v1/markets/active   Active markets                   │
│    GET /api/v1/markets/latest   Latest snapshots                 │
└──────────────────────────────────────────────────────────────────┘
        │                              │
   PostgreSQL :5432              Redis :6379
   markets                       (Sprint 3+)
   market_snapshots
```

### Data Flow

```
Every 5 seconds:

1. Binance Spot API
   GET /api/v3/ticker/24hr?symbols=[BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT]
   → last_price, bid, ask, volume

2. Polymarket CLOB API
   GET /markets (paginated)
   → filter: asset ∈ {BTC, ETH, SOL, XRP}
   → filter: timeframe ∈ {5m, 15m, 1H}
   → yes_price, no_price, liquidity, volume

3. Merge & Persist
   save_market()    → upsert to markets table
   save_snapshot()  → append to market_snapshots
```

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

### 1. Copy environment file

```bash
cp .env.example .env
```

### 2. Start all services with Docker

```bash
docker-compose up --build
```

The API will be available at **http://localhost:8000**.

### 3. Verify it's running

```bash
# Basic health
curl http://localhost:8000/api/v1/health

# Detailed health (DB + Redis)
curl http://localhost:8000/api/v1/health/detailed

# Active markets (populated after first collector tick)
curl http://localhost:8000/api/v1/markets/active

# Latest snapshots
curl http://localhost:8000/api/v1/markets/latest
```

---

## API Reference

| Method | Path                      | Description                                |
|--------|---------------------------|--------------------------------------------|
| GET    | `/api/v1/health`          | Basic health check — status, version, uptime |
| GET    | `/api/v1/health/detailed` | Health with DB + Redis status              |
| GET    | `/api/v1/markets`         | All markets (all statuses)                 |
| GET    | `/api/v1/markets/active`  | Active markets only                        |
| GET    | `/api/v1/markets/latest`  | Latest snapshots (default: 50)             |
| GET    | `/api/docs`               | Swagger UI                                 |
| GET    | `/api/redoc`              | ReDoc UI                                   |

### Health response (Sprint 2)

```json
{
  "status": "healthy",
  "version": "0.2.0",
  "uptime_seconds": 142.5
}
```

### Market response

```json
{
  "id": 1,
  "asset": "BTC",
  "timeframe": "5m",
  "polymarket_market_id": "0xabc...",
  "title": "Will BTC be above $70k in 5m?",
  "start_time": "2026-06-18T05:00:00Z",
  "end_time": "2026-06-18T06:00:00Z",
  "status": "active"
}
```

### Snapshot response

```json
{
  "id": 1,
  "market_id": 1,
  "timestamp": "2026-06-18T05:00:05Z",
  "yes_price": 0.72,
  "no_price": 0.28,
  "liquidity": 48000.0,
  "volume": 12300.0,
  "binance_price": 65432.10
}
```

---

## Docker Commands

```bash
# Start (development — hot reload)
docker-compose up --build

# Start in background
docker-compose up -d --build

# Stop
docker-compose down

# Full reset (removes volumes)
docker-compose down -v

# Logs
docker-compose logs -f
docker-compose logs -f backend

# Shell access
docker-compose exec backend bash
docker-compose exec postgres psql -U postgres -d polymarket
docker-compose exec redis redis-cli

# Production
docker-compose -f docker-compose.yml -f deployment/docker-compose.prod.yml up -d
```

---

## Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Expected output: **15 passed**

Test coverage:
- `test_health.py`         — health endpoint schema + status codes
- `test_binance_collector.py` — collector parsing with mock HTTP transport
- `test_market_repository.py` — save/update/query against in-memory SQLite

---

## Environment Variables

| Variable                    | Default                   | Description                        |
|-----------------------------|---------------------------|------------------------------------|
| `DATABASE_URL`              | `postgresql+asyncpg://...`| PostgreSQL DSN (asyncpg driver)    |
| `REDIS_URL`                 | `redis://localhost:6379/0`| Redis DSN                          |
| `APP_ENV`                   | `development`             | Environment name                   |
| `LOG_LEVEL`                 | `INFO`                    | Log verbosity                      |
| `LOG_FORMAT`                | `json`                    | `json` or `console`                |
| `DEBUG`                     | `false`                   | SQLAlchemy echo                    |
| `COLLECTOR_INTERVAL_SECONDS`| `5`                       | Data collection frequency          |
| `COLLECTOR_ENABLED`         | `true`                    | Enable/disable background scheduler|

---

## Sprint Roadmap

| Sprint | Status      | Scope                                                      |
|--------|-------------|------------------------------------------------------------|
| 1      | ✅ Complete | Infrastructure, Docker, FastAPI, DB/Redis connections      |
| 2      | ✅ Complete | Binance + Polymarket collectors, ORM models, scheduler, API |
| 3      | Planned     | Binance Futures + Chainlink collectors, Alembic migrations  |
| 4      | Planned     | Analysis services                                          |
