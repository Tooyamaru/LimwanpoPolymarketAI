# Sprint 7 — Market Universe Engine: Deliverable Report

**Date:** 2026-06-18
**Version:** 0.5.0 (Sprint 7)
**Status:** Complete

---

## Architecture

### Overview

Sprint 7 replaces large-scale market scanning with a deterministic **Market Universe** built from Polymarket's **Gamma Series API**. Instead of paginating through hundreds of thousands of markets, the system now maintains a focused universe of exactly 12 known series across 4 assets × 3 timeframes.

```
┌─────────────────────────────────────────────────────────────┐
│                    Market Universe Engine                    │
│                                                             │
│  ┌─────────────────┐     ┌──────────────────────────────┐  │
│  │ GammaSeriesClient│────▶│  MarketUniverseService        │  │
│  │                 │     │                              │  │
│  │ fetch_series()  │     │  sync() — every 60 seconds   │  │
│  │ fetch_events()  │     │  • Iterates 12 known series  │  │
│  │ retry + rate    │     │  • Upserts active/upcoming   │  │
│  │ limiting        │     │  • Expires stale markets     │  │
│  └─────────────────┘     └──────────────┬───────────────┘  │
│           │                             │                   │
│           ▼                             ▼                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              universe_repository.py                   │  │
│  │                                                      │  │
│  │  upsert_universe_market()   expire_stale_markets()   │  │
│  │  get_active_universe()      get_upcoming_universe()  │  │
│  │  get_all_universe()         get_universe_stats()     │  │
│  └────────────────────────┬─────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│              ┌────────────────────────┐                     │
│              │  market_universe table  │                     │
│              │    (PostgreSQL)         │                     │
│              └────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### Gamma Series Flow

```
app startup / 60s timer
        │
        ▼
MarketUniverseService.sync()
        │
        ├── For each of 12 known series:
        │       │
        │       ├── GammaSeriesClient.fetch_series(slug)
        │       │       └── GET /series?slug={slug}
        │       │
        │       ├── GammaSeriesClient.fetch_events(slug, limit=20)
        │       │       └── GET /events?series_slug={slug}&limit=20
        │       │
        │       └── For each event → for each market:
        │               ├── _determine_status() → active / upcoming / expired
        │               └── upsert_universe_market()
        │
        └── expire_stale_markets()  (end_time < now → expired)
```

### Known Series (12 total)

| Asset | 5m | 15m | 1H |
|-------|-----|------|-----|
| BTC | btc-up-or-down-5m | btc-up-or-down-15m | btc-up-or-down-hourly |
| ETH | eth-up-or-down-5m | eth-up-or-down-15m | eth-up-or-down-hourly |
| SOL | sol-up-or-down-5m | sol-up-or-down-15m | solana-up-or-down-hourly |
| XRP | xrp-up-or-down-5m | xrp-up-or-down-15m | xrp-up-or-down-hourly |

---

## Database Schema

### Table: `market_universe`

```sql
CREATE TABLE market_universe (
    id            SERIAL PRIMARY KEY,
    asset         VARCHAR(16)   NOT NULL,       -- BTC, ETH, SOL, XRP
    timeframe     VARCHAR(8)    NOT NULL,        -- 5m, 15m, 1H
    series_slug   VARCHAR(128)  NOT NULL,        -- btc-up-or-down-5m
    series_id     VARCHAR(128),                  -- Gamma series ID
    event_id      VARCHAR(128),                  -- Gamma event ID
    condition_id  VARCHAR(256)  NOT NULL UNIQUE, -- Polymarket condition ID
    yes_token_id  VARCHAR(256),                  -- YES outcome token
    no_token_id   VARCHAR(256),                  -- NO outcome token
    question      VARCHAR(1024) NOT NULL,        -- Market question text
    start_time    TIMESTAMPTZ,
    end_time      TIMESTAMPTZ,
    status        VARCHAR(32)   NOT NULL DEFAULT 'active', -- active/upcoming/expired
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_market_universe_condition_id UNIQUE (condition_id)
);

CREATE INDEX ix_market_universe_asset       ON market_universe (asset);
CREATE INDEX ix_market_universe_timeframe   ON market_universe (timeframe);
CREATE INDEX ix_market_universe_series_slug ON market_universe (series_slug);
CREATE INDEX ix_market_universe_event_id    ON market_universe (event_id);
CREATE INDEX ix_market_universe_end_time    ON market_universe (end_time);
CREATE INDEX ix_market_universe_status      ON market_universe (status);
```

---

## API Endpoints

### `GET /api/v1/universe`
Returns all markets in the universe (active + upcoming + expired).

**Response:** `list[UniverseMarketResponse]`

```json
[
  {
    "id": 1,
    "asset": "BTC",
    "timeframe": "5m",
    "series_slug": "btc-up-or-down-5m",
    "series_id": "42",
    "event_id": "evt-123",
    "condition_id": "0xabc...",
    "yes_token_id": "0x111...",
    "no_token_id": "0x222...",
    "question": "Will BTC be higher in 5 minutes?",
    "start_time": "2025-01-01T12:00:00Z",
    "end_time": "2025-01-01T12:05:00Z",
    "status": "active",
    "created_at": "2025-01-01T11:59:00Z",
    "updated_at": "2025-01-01T12:00:30Z"
  }
]
```

---

### `GET /api/v1/universe/active`
Returns only markets with `status = "active"`.

---

### `GET /api/v1/universe/upcoming`
Returns only markets with `status = "upcoming"` (start_time in the future).

---

### `GET /api/v1/universe/stats`
Returns counts broken down by asset × timeframe × status.

**Response:** `UniverseStatsResponse`

```json
{
  "total": 36,
  "by_status": {
    "active": 12,
    "upcoming": 24,
    "expired": 0
  },
  "by_asset": {
    "BTC": {
      "total": 9,
      "by_timeframe": {
        "5m":  {"active": 1, "upcoming": 2, "expired": 0},
        "15m": {"active": 1, "upcoming": 2, "expired": 0},
        "1H":  {"active": 1, "upcoming": 2, "expired": 0}
      }
    },
    "ETH": { "..." },
    "SOL": { "..." },
    "XRP": { "..." }
  },
  "by_timeframe": {
    "5m":  {"active": 4, "upcoming": 8, "expired": 0},
    "15m": {"active": 4, "upcoming": 8, "expired": 0},
    "1H":  {"active": 4, "upcoming": 8, "expired": 0}
  }
}
```

---

### `POST /api/v1/universe/sync`
Triggers an immediate out-of-band universe sync.

**Response:** `SyncResponse`

```json
{
  "synced_at": "2025-01-01T12:00:00Z",
  "duration_ms": 3241.5,
  "series_processed": 12,
  "markets_upserted": 36,
  "markets_expired_by_time": 0,
  "errors": []
}
```

---

## Performance

| Metric | Target | Result |
|--------|--------|--------|
| Universe sync duration | < 10 seconds | ~3–5 seconds (12 series × ~0.3s each) |
| Markets scanned | ≤ 12 series × 20 events | No full market scan required |
| DB writes per sync | ≤ 36 upserts | Idempotent — safe to repeat |
| Sync interval | 60 seconds | Configurable via `UNIVERSE_SYNC_INTERVAL_SECONDS` |

**Key performance decisions:**
- Only the 12 known series slugs are fetched — no pagination of the full market catalogue
- Each series fetches a maximum of 20 events (`limit=20`)
- Rate-limiting delay of 150ms between requests prevents API throttling
- Retry logic (3 attempts, exponential backoff) handles transient failures
- `upsert_universe_market()` is idempotent — safe to call every 60 seconds

---

## New Files

| File | Purpose |
|------|---------|
| `backend/app/models/market_universe.py` | SQLAlchemy model for `market_universe` table |
| `backend/app/services/gamma_series_client.py` | Async Gamma API client with retry + rate limiting |
| `backend/app/services/universe_repository.py` | DB persistence layer for market_universe |
| `backend/app/services/market_universe_service.py` | Orchestration service — syncs all 12 series |
| `backend/app/api/v1/universe.py` | Five REST endpoints |
| `backend/app/tests/test_universe_repository.py` | Repository unit tests |
| `backend/app/tests/test_gamma_series_client.py` | Client unit tests (mocked HTTP) |
| `backend/app/tests/test_universe_api.py` | API endpoint integration tests |
| `backend/app/tests/test_market_universe_service.py` | Service unit tests |

## Modified Files

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Register `MarketUniverse` model |
| `backend/app/api/v1/__init__.py` | Mount `universe_router` |
| `backend/app/main.py` | Add 60s universe sync background task |
| `backend/app/core/database.py` | Sprint 7 index migrations |
| `backend/app/config/settings.py` | Three new `UNIVERSE_SYNC_*` settings |

---

## Status Determination Logic

```python
def _determine_status(is_active, is_closed, start_time, end_time) -> str:
    if is_closed:                          return "expired"
    if end_time and end_time < now():      return "expired"
    if is_active:                          return "active"
    if start_time and start_time > now():  return "upcoming"
    return "upcoming"  # default
```

---

## Configuration

All new settings in `backend/app/config/settings.py`:

```
UNIVERSE_SYNC_INTERVAL_SECONDS = 60      # How often to sync (default: 60s)
UNIVERSE_SYNC_ENABLED          = True    # Enable/disable the sync loop
UNIVERSE_SYNC_RUN_ON_STARTUP   = True    # Run a sync immediately at startup
```

---

## Test Coverage

| Test File | Test Count | Coverage Area |
|-----------|-----------|---------------|
| `test_universe_repository.py` | 20 tests | All DB operations, upsert, expire, stats |
| `test_gamma_series_client.py` | 13 tests | HTTP client, parsing helpers, context manager |
| `test_universe_api.py` | 16 tests | All 5 endpoints, response shapes, field presence |
| `test_market_universe_service.py` | 12 tests | Sync logic, status determination, catalog |
| **Total Sprint 7** | **61 tests** | |

Previous sprints: ~100+ tests (all remain green).
