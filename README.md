# Polymarket Quant Bot

Production-grade quantitative trading infrastructure for Polymarket prediction markets, with data feeds from Binance (Spot & Futures) and Chainlink price oracles.

---

## Project Structure

```
polymarket-quant-bot/
│
├── backend/                        # FastAPI Python backend
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py     # API router registry
│   │   │       └── health.py       # GET /api/v1/health
│   │   ├── collector/              # Data ingestion modules (Sprint 2)
│   │   │   ├── __init__.py
│   │   │   ├── binance_spot.py     # Binance Spot WebSocket collector
│   │   │   ├── binance_futures.py  # Binance Futures collector
│   │   │   ├── polymarket.py       # Polymarket CLOB collector
│   │   │   └── chainlink.py        # Chainlink oracle collector
│   │   ├── core/
│   │   │   ├── database.py         # SQLAlchemy async engine + session
│   │   │   ├── logging.py          # Structured JSON logging (structlog)
│   │   │   └── redis.py            # Async Redis connection pool
│   │   ├── models/                 # SQLAlchemy ORM models (Sprint 2)
│   │   ├── services/               # Business logic layer (Sprint 2)
│   │   ├── config/
│   │   │   └── settings.py         # Pydantic Settings management
│   │   ├── tests/
│   │   │   ├── conftest.py         # Pytest fixtures
│   │   │   └── test_health.py      # Health endpoint tests
│   │   └── main.py                 # FastAPI application factory
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   └── pyproject.toml
│
├── frontend/                       # Frontend (Sprint 3+)
│
├── database/
│   ├── init/
│   │   └── 01_extensions.sql       # PostgreSQL extensions
│   └── migrations/                 # Alembic migrations (Sprint 2)
│
├── deployment/
│   └── docker-compose.prod.yml     # Production Docker overrides
│
├── docs/
│   └── architecture.md             # System architecture diagrams
│
├── docker-compose.yml              # Development Docker Compose
├── .env.example                    # Environment variable template
├── .gitignore
└── README.md
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

---

## Quick Start

### 1. Copy environment file

```bash
cp .env.example .env
# Edit .env with your values if needed
```

### 2. Start all services with Docker

```bash
docker-compose up --build
```

The API will be available at **http://localhost:8000**.

### 3. Verify it's running

```bash
curl http://localhost:8000/api/v1/health
# {"status":"healthy"}
```

---

## API Endpoints

| Method | Path                    | Description                              |
|--------|-------------------------|------------------------------------------|
| GET    | `/api/v1/health`        | Basic health check                       |
| GET    | `/api/v1/health/detailed` | Health with DB + Redis status          |
| GET    | `/api/docs`             | Swagger UI (dev only)                    |
| GET    | `/api/redoc`            | ReDoc UI (dev only)                      |

### Health response

```json
{ "status": "healthy" }
```

### Detailed health response

```json
{
  "status": "healthy",
  "database": "healthy",
  "redis": "healthy",
  "version": "0.1.0"
}
```

---

## Docker Commands

### Start services (development — with hot reload)

```bash
docker-compose up --build
```

### Start services in background

```bash
docker-compose up -d --build
```

### Stop services

```bash
docker-compose down
```

### Stop services and remove volumes (full reset)

```bash
docker-compose down -v
```

### View logs

```bash
# All services
docker-compose logs -f

# Single service
docker-compose logs -f backend
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Rebuild only the backend

```bash
docker-compose up --build backend
```

### Production deployment

```bash
docker-compose -f docker-compose.yml -f deployment/docker-compose.prod.yml up -d
```

### Shell access

```bash
# Backend container
docker-compose exec backend bash

# PostgreSQL REPL
docker-compose exec postgres psql -U postgres -d polymarket

# Redis CLI
docker-compose exec redis redis-cli
```

---

## Local Development (without Docker)

### Prerequisites

- Python 3.12
- PostgreSQL 16 running locally
- Redis 7 running locally

### Install dependencies

```bash
cd backend
pip install -r requirements-dev.txt
```

### Run the API

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run tests

```bash
cd backend
pytest
```

---

## Environment Variables

| Variable          | Default                                              | Description                    |
|-------------------|------------------------------------------------------|--------------------------------|
| `DATABASE_URL`    | `postgresql+asyncpg://postgres:postgres@localhost:5432/polymarket` | PostgreSQL DSN |
| `REDIS_URL`       | `redis://localhost:6379/0`                           | Redis DSN                      |
| `APP_ENV`         | `development`                                        | Environment name               |
| `LOG_LEVEL`       | `INFO`                                               | Log verbosity                  |
| `LOG_FORMAT`      | `json`                                               | `json` or `console`            |
| `DEBUG`           | `false`                                              | Enable SQLAlchemy echo         |

---

## Sprint Roadmap

| Sprint | Status      | Scope                                                     |
|--------|-------------|-----------------------------------------------------------|
| 1      | ✅ Complete | Infrastructure, Docker, FastAPI, DB/Redis connections     |
| 2      | Planned     | Data collectors (Binance Spot/Futures, Polymarket, Chainlink) |
| 3      | Planned     | ORM models, data normalisation, persistence               |
| 4      | Planned     | Analysis services                                         |
