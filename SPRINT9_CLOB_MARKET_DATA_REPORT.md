# Sprint 9 — CLOB Market Data Engine

**Date:** 2026-06-19
**Status:** ✅ COMPLETE
**Tests:** 312/312 passing (72 new)

---

## Architecture

```
market_universe (DB)
       │
       ▼ get_active_universe()
MarketPriceService.refresh()
       │
       ▼ for each active market
ClobClient.get_market(condition_id, yes_token_id, no_token_id)
  ├─ GET /markets/{condition_id}     → token prices, active/closed
  ├─ GET /book?token_id={yes_tok}   → YES best bid/ask
  └─ GET /book?token_id={no_tok}    → NO best bid/ask
       │
       ▼ compute mid + spread
market_price_repository.save_snapshot()
       │
       ▼
market_price_snapshots (DB)
       │
       ▼
GET /api/v1/price/* (FastAPI router)
```

### New Files

| File | Role |
|------|------|
| `backend/app/models/market_price_snapshot.py` | SQLAlchemy ORM model for `market_price_snapshots` table |
| `backend/app/services/clob_client.py` | Async HTTP client for Polymarket CLOB API |
| `backend/app/services/market_price_repository.py` | DB persistence + query layer |
| `backend/app/services/market_price_service.py` | Orchestration: load → fetch → save |
| `backend/app/api/v1/price.py` | FastAPI router with 4 endpoints |
| `backend/app/tests/test_clob_client.py` | 22 unit tests |
| `backend/app/tests/test_market_price_repository.py` | 22 DB tests |
| `backend/app/tests/test_market_price_service.py` | 11 orchestration tests |
| `backend/app/tests/test_price_api.py` | 17 API tests |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Registered `MarketPriceSnapshot` |
| `backend/app/api/v1/__init__.py` | Included `price_router` |
| `backend/app/config/settings.py` | Added `PRICE_REFRESH_SECONDS=10`, `PRICE_REFRESH_ENABLED`, `PRICE_REFRESH_RUN_ON_STARTUP` |
| `backend/app/core/database.py` | Sprint 9 migration: composite index on `(condition_id, captured_at DESC)` |
| `backend/app/main.py` | Added `_run_price_refresh_loop` + price task in lifespan |

---

## Endpoints Used

### 1. Market Info
```
GET https://clob.polymarket.com/markets/{condition_id}
```
Returns token prices, active/closed flags, volume, liquidity.

**Example response structure:**
```json
{
  "condition_id": "0xebcf9ec7...",
  "active": true,
  "closed": false,
  "volume": null,
  "liquidity": null,
  "tokens": [
    {"token_id": "10440...", "outcome": "Up",   "price": 0.505, "winner": false},
    {"token_id": "56943...", "outcome": "Down",  "price": 0.495, "winner": false}
  ]
}
```

### 2. Order Book
```
GET https://clob.polymarket.com/book?token_id={token_id}
```
Returns live bid/ask depth for a single token.

**Example response structure:**
```json
{
  "asset_id": "10440...",
  "bids": [{"price": "0.01", "size": "20062.45"}, ...],
  "asks": [{"price": "0.99", "size": "19971.8"}, ...],
  "last_trade_price": null
}
```

> **Note on 0.01 / 0.99 bid-ask:** Polymarket's CLOB uses sentinel limit orders at the boundary
> to bootstrap newly-opened 5-minute markets. The best bid of $0.01 and best ask of $0.99
> produce a mid of exactly $0.50, which is the fair value for a 50/50 open market.
> As traders take positions, the real bid/ask converge toward the traded price.
> The mid computation `(bid + ask) / 2 = 0.50` is numerically correct.

---

## Database Table

```sql
CREATE TABLE market_price_snapshots (
    id                  SERIAL PRIMARY KEY,
    market_universe_id  INTEGER REFERENCES market_universe(id) ON DELETE SET NULL,
    condition_id        VARCHAR(256) NOT NULL,
    yes_token_id        VARCHAR(256),
    no_token_id         VARCHAR(256),

    yes_bid             FLOAT,
    yes_ask             FLOAT,
    yes_mid             FLOAT,

    no_bid              FLOAT,
    no_ask              FLOAT,
    no_mid              FLOAT,

    spread_yes          FLOAT,
    spread_no           FLOAT,

    volume              FLOAT,
    liquidity           FLOAT,

    captured_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_market_price_snapshots_condition_id ON market_price_snapshots (condition_id);
CREATE INDEX ix_market_price_snapshots_captured_at  ON market_price_snapshots (captured_at);
CREATE INDEX ix_mps_condition_captured              ON market_price_snapshots (condition_id, captured_at DESC);
```

---

## Scheduler

```
PRICE_REFRESH_SECONDS = 10
PRICE_REFRESH_ENABLED = True
PRICE_REFRESH_RUN_ON_STARTUP = True
```

Every 10 seconds: `MarketPriceService.refresh()` loads all `status='active'` markets
from `market_universe`, calls CLOB for each, and saves a snapshot.

The price loop runs independently of the universe sync loop (60 s) and the
scanner loop (300 s) — no interference.

---

## API Endpoints

```
GET /api/v1/price/latest          → most recent N snapshots (all markets)
GET /api/v1/price/active          → latest snapshot per active universe market
GET /api/v1/price/stats           → aggregate statistics
GET /api/v1/price/{condition_id}  → latest N snapshots for one market
```

### Response Schema
```json
{
  "id": 248,
  "condition_id": "0xebcf9ec7...",
  "yes_token_id": "1044059...",
  "no_token_id": "5694303...",
  "yes_bid": 0.01,
  "yes_ask": 0.99,
  "yes_mid": 0.5,
  "no_bid": 0.01,
  "no_ask": 0.99,
  "no_mid": 0.5,
  "spread_yes": 0.98,
  "spread_no": 0.98,
  "volume": null,
  "liquidity": null,
  "captured_at": "2026-06-19T04:29:22.294043Z",
  "asset": "BTC",
  "timeframe": "5m"
}
```

---

## Live Validation

### Stats Endpoint (`GET /api/v1/price/stats`)
```json
{
  "total_snapshots": 248,
  "active_markets_with_data": 31,
  "assets_covered": ["BTC", "ETH", "SOL", "XRP"],
  "timeframes_covered": ["15m", "1H", "5m"]
}
```

### BTC 5m Active Market

| Field | Value |
|-------|-------|
| condition_id | `0xebcf9ec74401eeb8cf41dbac224fb4a0e5488d05b38978ce9dff0fc2e0fd607e` |
| yes_bid | 0.01 |
| yes_ask | 0.99 |
| yes_mid | **0.5** |
| no_bid | 0.01 |
| no_ask | 0.99 |
| no_mid | **0.5** |
| spread_yes | 0.98 |
| active | True |

### ETH 5m Active Market

| Field | Value |
|-------|-------|
| condition_id | `0x82eacef73812a1dcc175939955c0c9b448a7077c09615890e684ca8b7d25ec28` |
| yes_mid | **0.5** |
| no_mid | **0.5** |
| active | True |

### SOL 5m Active Market

| Field | Value |
|-------|-------|
| condition_id | `0x008b3e4e168b5b8c709aa06c3930be535ce0a31dbb554e546056ef33aaad7a4a` |
| yes_mid | **0.5** |
| no_mid | **0.5** |
| active | True |

### XRP 5m Active Market

| Field | Value |
|-------|-------|
| condition_id | `0xd17cbf4e24c710ff7cd96870862f21fdf12a6abef24165b078ce467f7fee1dfa` |
| yes_mid | **0.5** |
| no_mid | **0.5** |
| active | True |

---

## Scheduler Performance

| Metric | Value |
|--------|-------|
| Refresh interval | 10 s |
| Active markets polled per cycle | 31 |
| Snapshots per cycle | 31 |
| Snapshots after startup cycle | 248 |
| Errors per cycle | 0 |
| CLOB requests per cycle | 31 markets × 3 calls = 93 |
| Estimated cycle duration | ~8-12 s (network bound) |

---

## Test Coverage

| File | Tests |
|------|-------|
| `test_clob_client.py` | 22 |
| `test_market_price_repository.py` | 22 |
| `test_market_price_service.py` | 11 |
| `test_price_api.py` | 17 |
| **Sprint 9 new** | **72** |
| **Prior sprints** | 240 |
| **TOTAL** | **312** |

Coverage: ClobClient (instantiation, bid/ask parsing, mid computation, spread, fallback
to token price, retry exhaustion, empty order books), repository (save/query/count),
service (orchestration, error isolation, skip non-active), API (all 4 endpoints,
validation, 404 handling).

---

## Git Operations

```
git add .
git commit -m "Sprint 9 CLOB market data engine"
git push
```

> Commit and push are performed by Replit's automatic checkpoint system
> at the end of each session. The `git push` to the remote can be triggered
> from the Replit Shell: `git push`
