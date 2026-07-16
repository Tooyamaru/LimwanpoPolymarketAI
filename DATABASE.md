# DATABASE — Polymarket Quant Bot

PostgreSQL (asyncpg driver). Tables created via SQLAlchemy `create_all` + `ADD COLUMN IF NOT EXISTS` migrations on startup.

---

## Entity Relationship Diagram (Text)

```
markets (Layer 1)
  └─ id, symbol, market_name, …

market_universe (Layer 3)           ← primary active-market registry
  └─ condition_id (unique)
  └─ asset, timeframe, series_slug
  └─ status: ACTIVE | UPCOMING | EXPIRED

market_price_snapshots (Layer 3b)   ← CLOB live prices
  └─ condition_id (FK-like → market_universe)
  └─ yes_mid, yes_bid, yes_ask, spread_yes, …

signals (Layer 4)
  └─ condition_id, asset, timeframe
  └─ signal_type, severity
  └─ yes_mid_delta, spread_delta, seed_deviation

opportunities (Layer 5)
  └─ condition_id (unique — UPSERT)
  └─ opportunity_score (0–100)
  └─ score components × 5
  └─ direction: BUY_YES | BUY_NO | NEUTRAL

trade_decisions (Layer 6)
  └─ condition_id, decision, status, opportunity_score
  └─ status: PENDING → RISK_APPROVED | BLOCKED → EXECUTED
  └─ append-only (new row per strategy evaluation)

risk_events (Layer 9)               ← new
  └─ decision_id (FK → trade_decisions.id)
  └─ result: ALLOW | BLOCK
  └─ reason: DUPLICATE_POSITION | MAX_OPEN_POSITIONS | MAX_EXPOSURE | DAILY_LOSS | DAILY_TRADES
  └─ open_positions_count, daily_loss, daily_trades (snapshot at check time)

orders (Layer 7)
  └─ decision_id (FK → trade_decisions.id)
  └─ side: LONG_YES | LONG_NO
  └─ filled_price, status: FILLED (paper mode)
  └─ append-only

positions (Layer 8)
  └─ order_id (FK unique → orders.id)
  └─ entry_price = fill_price
  └─ current_price (updated every 30s from opportunities)
  └─ unrealized_pnl = quantity × (current_price − entry_price)
  └─ status: OPEN → CLOSED
```

---

## Tables

### `market_universe`
Primary active-market registry. 12 active markets at any time (4 assets × 3 timeframes).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PK | |
| condition_id | VARCHAR(256) | UNIQUE NOT NULL | Polymarket CLOB market ID |
| asset | VARCHAR(16) | NOT NULL | BTC, ETH, SOL, XRP |
| timeframe | VARCHAR(8) | NOT NULL | 5m, 15m, 1H |
| series_slug | VARCHAR(128) | NOT NULL | Gamma series identifier |
| series_id | VARCHAR(128) | | |
| event_id | VARCHAR(128) | | |
| yes_token_id | VARCHAR(128) | | |
| no_token_id | VARCHAR(128) | | |
| question | TEXT | NOT NULL | Market question text |
| start_time | TIMESTAMPTZ | | |
| end_time | TIMESTAMPTZ | | Market expiry |
| status | VARCHAR(16) | NOT NULL | ACTIVE \| UPCOMING \| EXPIRED |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**Indexes:** `status`, `end_time`, `(asset, timeframe)`, `condition_id UNIQUE`

---

### `market_price_snapshots`
Live CLOB bid/ask snapshots. One row per fetch cycle per active market (~every 10s).

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| condition_id | VARCHAR(256) | |
| asset | VARCHAR(16) | |
| timeframe | VARCHAR(8) | |
| yes_mid | FLOAT | (yes_bid + yes_ask) / 2 |
| yes_bid | FLOAT | Best bid for YES token |
| yes_ask | FLOAT | Best ask for YES token |
| no_mid | FLOAT | 1 − yes_mid |
| spread_yes | FLOAT | yes_ask − yes_bid |
| seed_deviation | FLOAT | Distance from 0.5 seed price |
| best_bid_size | FLOAT | |
| best_ask_size | FLOAT | |
| captured_at | TIMESTAMPTZ | |

**Indexes:** `(condition_id, captured_at DESC)` composite

---

### `signals`
Price movement signals emitted by the Signal Engine every 10s.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| condition_id | VARCHAR(256) | |
| asset, timeframe | VARCHAR | |
| signal_type | VARCHAR(32) | MID_MOVE, SPREAD_COMPRESSION, SEED_DEVIATION |
| severity | VARCHAR(16) | LOW, MEDIUM, HIGH |
| yes_mid_before/after/delta | FLOAT | |
| spread_before/after/delta | FLOAT | |
| seed_deviation | FLOAT | |
| snapshot_id_before/after | INT | |
| detected_at | TIMESTAMPTZ | |

---

### `opportunities`
One row per active market. UPSERT on every Opportunity Engine cycle (30s).

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| condition_id | VARCHAR(256) UNIQUE | |
| asset, timeframe | VARCHAR | |
| opportunity_score | FLOAT | 0–100 composite |
| score_mid_movement | FLOAT | Component (0–20) |
| score_spread | FLOAT | Component (0–20) |
| score_depth_imbalance | FLOAT | Component (0–20) |
| score_signal_activity | FLOAT | Component (0–20) |
| score_discovery | FLOAT | Component (0–20) |
| yes_mid/bid/ask | FLOAT | Latest CLOB prices |
| no_mid | FLOAT | |
| spread_yes/no | FLOAT | |
| seed_deviation | FLOAT | |
| signal_count_1h | INT | Signals in last hour |
| last_signal_type/severity | VARCHAR | |
| minutes_to_expiry | FLOAT | |
| direction | VARCHAR(16) | BUY_YES \| BUY_NO \| NEUTRAL |
| evaluated_at | TIMESTAMPTZ | |

---

### `trade_decisions`
Append-only strategy decisions. New row per strategy cycle.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| condition_id | VARCHAR(256) | |
| asset, timeframe | VARCHAR | |
| decision | VARCHAR(32) | OPEN_LONG_YES \| OPEN_LONG_NO \| WATCH \| SKIP |
| status | VARCHAR(16) | PENDING → RISK_APPROVED \| BLOCKED → EXECUTED |
| opportunity_score | FLOAT | |
| direction | VARCHAR(16) | BUY_YES \| BUY_NO \| NEUTRAL |
| yes_mid/bid/ask | FLOAT | Prices at decision time |
| spread_yes | FLOAT | |
| skip_reason | VARCHAR(64) | LOW_SCORE \| HIGH_SPREAD \| NEUTRAL_DIRECTION |
| decided_at | TIMESTAMPTZ | |

---

### `risk_events`
Append-only risk evaluation log. One row per decision screened by Risk Engine.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| decision_id | INT | FK → trade_decisions.id |
| condition_id | VARCHAR(256) | |
| asset, timeframe | VARCHAR | |
| result | VARCHAR(16) | ALLOW \| BLOCK |
| reason | VARCHAR(64) | NULL if ALLOW; rule name if BLOCK |
| checked_at | TIMESTAMPTZ | |
| open_positions_count | INT | Portfolio state snapshot |
| daily_loss | FLOAT | Sum of unrealized PnL today |
| daily_trades | INT | Orders placed today |

**Indexes:** `result`, `decision_id`, `(asset, timeframe)`, `checked_at`

---

### `orders`
Append-only paper order fills. One row per executed RISK_APPROVED decision.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| decision_id | INT | FK → trade_decisions.id |
| condition_id | VARCHAR(256) | |
| asset, timeframe | VARCHAR | |
| side | VARCHAR(16) | LONG_YES \| LONG_NO |
| order_type | VARCHAR(16) | MARKET (paper mode) |
| quantity | FLOAT | Always 1.0 in paper mode |
| requested_price | FLOAT | Best ask at decision time |
| filled_price | FLOAT | = requested_price (no slippage) |
| status | VARCHAR(16) | FILLED (paper mode instant fill) |
| created_at | TIMESTAMPTZ | |
| filled_at | TIMESTAMPTZ | |

---

### `positions`
Active paper positions. One row per FILLED order.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| order_id | INT UNIQUE | FK → orders.id (one position per fill) |
| condition_id | VARCHAR(256) | |
| asset, timeframe | VARCHAR | |
| side | VARCHAR(16) | LONG_YES \| LONG_NO |
| quantity | FLOAT | |
| entry_price | FLOAT | fill_price at open |
| current_price | FLOAT | Updated every 30s from opportunities |
| unrealized_pnl | FLOAT | quantity × (current_price − entry_price) |
| realized_pnl | FLOAT | Set on CLOSED |
| status | VARCHAR(16) | OPEN \| CLOSED |
| opened_at | TIMESTAMPTZ | |
| closed_at | TIMESTAMPTZ | |

---

## Foreign Keys (Logical)

| Child Table | Column | Parent Table | Status |
|-------------|--------|--------------|--------|
| orders | decision_id | trade_decisions.id | Index only (not FK constraint) |
| risk_events | decision_id | trade_decisions.id | Index only (not FK constraint) |
| positions | order_id | orders.id | UNIQUE index, not FK constraint |

> Note: FK constraints are not declared in SQLAlchemy models to allow append-only inserts
> without SQLAlchemy relationship overhead. Referential integrity enforced by application logic.

---

## Migration Strategy

No Alembic. Schema is maintained via `init_db()` in `core/database.py`:
1. `create_all()` — creates all tables from ORM metadata on first run
2. `ADD COLUMN IF NOT EXISTS` — additive column migrations (safe to replay on restart)
3. `CREATE INDEX IF NOT EXISTS` — index migrations (safe to replay)

This approach is suitable for a single-developer project. Alembic migration files can be
added if the team grows or schema changes become complex.
