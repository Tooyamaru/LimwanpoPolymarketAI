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
│   │   │       ├── __init__.py                     # Router registry
│   │   │       ├── health.py                       # GET /api/v1/health
│   │   │       ├── markets.py                      # GET /api/v1/markets/*
│   │   │       ├── discovery.py                    # GET /api/v1/discovery/*
│   │   │       ├── scanner.py                      # GET /api/v1/scanner/*
│   │   │       └── classifier.py                   # GET /api/v1/classifier/*
│   │   ├── collector/
│   │   │   ├── binance_spot.py                     # Binance Spot ticker
│   │   │   ├── polymarket.py                       # Polymarket CLOB prices
│   │   │   └── scheduler.py                        # 5-second price tick
│   │   ├── core/
│   │   │   ├── database.py                         # SQLAlchemy async engine
│   │   │   ├── logging.py                          # structlog JSON
│   │   │   └── redis.py                            # Async Redis pool
│   │   ├── models/
│   │   │   ├── market.py
│   │   │   ├── market_snapshot.py
│   │   │   ├── scanner_market.py                   # Scanner universe
│   │   │   ├── discovery_run.py                    # Per-run diagnostics
│   │   │   └── event_classification.py             # ← Sprint 4
│   │   ├── services/
│   │   │   ├── market_repository.py
│   │   │   ├── market_discovery.py                 # Full market scan + classify
│   │   │   ├── scanner.py                          # UPDOWN-only universe
│   │   │   ├── scanner_repository.py
│   │   │   ├── event_classifier.py                 # ← Sprint 4
│   │   │   └── event_classification_repository.py  # ← Sprint 4
│   │   ├── config/settings.py
│   │   ├── tests/
│   │   │   ├── test_health.py
│   │   │   ├── test_binance_collector.py
│   │   │   ├── test_market_repository.py
│   │   │   ├── test_market_discovery.py
│   │   │   ├── test_scanner_repository.py
│   │   │   ├── test_scanner.py
│   │   │   ├── test_event_classifier.py            # ← Sprint 4 (48 tests)
│   │   │   └── test_event_classification_repository.py  # ← Sprint 4 (8 tests)
│   │   └── main.py
│   ├── requirements.txt
│   ├── pytest.ini
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Sprint 4 Architecture — Event Classification Layer

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application v0.4.0                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │   Price Collector  (every 5s)                                       │   │
│  │   Binance Spot → PostgreSQL snapshots                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │   Market Scanner   (every 300s + on startup)                        │   │
│  │                                                                     │   │
│  │   ① MarketDiscoveryService                                          │   │
│  │       Paginate ALL Polymarket markets                               │   │
│  │       For EVERY market → EventClassifier.classify(title)           │   │
│  │       Accumulate global counts: UPDOWN/PRICE_RANGE/NEWS/POLITICS   │   │
│  │       Asset+timeframe filter → matched_markets                     │   │
│  │              │                                                      │   │
│  │   ② ScannerService                                                  │   │
│  │       All matched markets → event_classifications table            │   │
│  │       UPDOWN only → scanner_markets table (active universe)        │   │
│  │       Store aggregate class counts → discovery_runs               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  REST API                                                                   │
│    GET /api/v1/health                  Version + uptime                    │
│    GET /api/v1/markets                 Price universe                      │
│    GET /api/v1/discovery               Latest discovery run stats          │
│    POST /api/v1/discovery/run          On-demand full scan                 │
│    GET /api/v1/discovery/markets       All matched markets + transparency  │
│    GET /api/v1/scanner                 Full UPDOWN scanner universe        │
│    GET /api/v1/scanner/active          Active UPDOWN markets               │
│    GET /api/v1/scanner/stats           Stats by asset/health               │
│    GET /api/v1/classifier              All classified markets              │
│    GET /api/v1/classifier/updown       UPDOWN markets only                │
│    GET /api/v1/classifier/stats        Classification breakdown (250k+)   │
└─────────────────────────────────────────────────────────────────────────────┘
            │
     PostgreSQL tables
       markets
       market_snapshots
       scanner_markets         ← UPDOWN universe only (Sprint 3/4)
       discovery_runs          ← per-run stats + classification counts
       event_classifications   ← Sprint 4: every matched market + event type
```

---

## EventClassifier — Classification Rules

Priority order: **UPDOWN > PRICE_RANGE > NEWS_EVENT > POLITICS > OTHER**

### UPDOWN (highest priority — what we actually trade)

Target markets:
- `BTC Up or Down 5 Minutes`
- `ETH Up or Down 15 Minutes`
- `SOL Up or Down 1 Hour`
- `XRP Up or Down 1 Hour`

| Rule | Pattern | Example |
|---|---|---|
| `updown_phrase` | `\bup\s+or\s+down\b` | "BTC Up or Down in 5m?" |
| `downup_phrase` | `\bdown\s+or\s+up\b` | "ETH Down or Up 15min?" |
| `updown_slash`  | `\bup/down\b` | "SOL Up/Down 1H" |
| `updown_hyphen` | `\bup-or-down\b` | "XRP up-or-down market" |
| `updown_compound`| `\bupdown\b` | "BTC updown 5m" |

**Confidence levels:**

| Context | Confidence |
|---|---|
| Caller confirmed asset + timeframe | 0.95 |
| Asset + timeframe detectable in title | 0.90 |
| Asset or timeframe (one signal) | 0.80 |
| Phrase only, no asset/timeframe | 0.65 |

### PRICE_RANGE

Triggered by: `above`, `below`, `over`, `under`, `between`, `$X`, `> X`, `< X`, `hit`, `reach`, `exceed`, `break`

### NEWS_EVENT

Triggered by: `etf`, `halving`, `fork`, `sec`, `regulation`, `hack`, `launch`, `upgrade`, `mainnet`, `airdrop`, `approval`, `listing`, `ban`, `crash`, `rate cut`, `fed`, `cpi`, `interest rate`

### POLITICS

Triggered by: `election`, `president`, `trump`, `biden`, `harris`, `congress`, `senate`, `democrat`, `republican`, `votes?`, `voting`, `governor`, `primary`, `ballot`, `war`, `nato`, `government`, `minister`, `parliament`

---

## All Sprints

| Sprint | Status | Description |
|---|---|---|
| 1 | ✅ | Infrastructure: FastAPI, Docker, PostgreSQL, Redis |
| 2 | ✅ | Data Collection: Binance Spot, Polymarket prices, 5s scheduler |
| 3 | ✅ | Discovery & Scanner: full market scan, universe builder |
| 4 | ✅ | Event Classification: UPDOWN/PRICE_RANGE/NEWS/POLITICS/OTHER |
| 5 | 🔜 | Analysis services |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Cache | Redis 7 |
| HTTP Client | httpx (async) |
| Logging | structlog JSON |
| Config | pydantic-settings |
| Testing | pytest + anyio + aiosqlite |

---

## Running Tests

```bash
cd backend
pytest
```

**Sprint 4 target: 91 tests passed**

| Test Module | Tests | Coverage |
|---|---|---|
| `test_health.py` | 4 | Health endpoint schema + status |
| `test_binance_collector.py` | 6 | Collector with mock HTTP |
| `test_market_repository.py` | 5 | Market CRUD (SQLite) |
| `test_market_discovery.py` | 16 | Discovery matching + mock HTTP |
| `test_scanner_repository.py` | 8 | Scanner CRUD + stale marking |
| `test_scanner.py` | 4 | Scanner orchestration |
| `test_event_classifier.py` | 40 | Full classifier coverage |
| `test_event_classification_repository.py` | 8 | Classification CRUD |
| **Total** | **91** | |

---

## Full API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Status, version, uptime |
| GET | `/api/v1/health/detailed` | DB + Redis dependency health |
| GET | `/api/v1/markets` | All tracked markets |
| GET | `/api/v1/markets/active` | Active markets only |
| GET | `/api/v1/markets/latest` | Latest price snapshots |
| GET | `/api/v1/discovery` | Latest discovery run diagnostics |
| POST | `/api/v1/discovery/run` | Trigger on-demand full market discovery |
| GET | `/api/v1/discovery/markets` | All matched markets with transparency |
| GET | `/api/v1/scanner` | Full UPDOWN scanner universe |
| GET | `/api/v1/scanner/active` | Active scanner markets |
| GET | `/api/v1/scanner/stats` | Aggregate stats by asset + health status |
| GET | `/api/v1/classifier` | All classified markets with transparency |
| GET | `/api/v1/classifier/updown` | UPDOWN markets only |
| GET | `/api/v1/classifier/stats` | Classification breakdown across all markets |
| GET | `/api/docs` | Swagger UI |

### Classifier stats response (Sprint 4)

```json
{
  "run_at": "2026-06-18T06:00:00Z",
  "total": 250000,
  "updown": 18,
  "price_range": 112,
  "news_event": 9000,
  "politics": 70000,
  "other": 170870
}
```

### Event classification response (Sprint 4)

```json
{
  "id": 1,
  "market_id": "0xabc...",
  "raw_title": "BTC Up or Down in 5m?",
  "event_type": "UPDOWN",
  "confidence": 0.95,
  "matched_rule": "updown_phrase",
  "created_at": "2026-06-18T06:00:00Z"
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(asyncpg)* | PostgreSQL DSN |
| `REDIS_URL` | `redis://…` | Redis DSN |
| `APP_ENV` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `COLLECTOR_INTERVAL_SECONDS` | `5` | Price tick frequency |
| `COLLECTOR_ENABLED` | `true` | Enable price collector |
| `SCANNER_INTERVAL_SECONDS` | `300` | Market universe refresh |
| `SCANNER_ENABLED` | `true` | Enable market scanner |
| `SCANNER_RUN_ON_STARTUP` | `true` | Immediate boot scan |
