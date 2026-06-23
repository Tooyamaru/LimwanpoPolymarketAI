# NEXT BUILD TASKS

---

## ✅ Layer 9 — Risk Engine COMPLETE (2026-06-23)

**Pipeline position:** Strategy Engine → **Risk Engine** → Execution Engine

**Files created:**
- `backend/app/models/risk_event.py` — `risk_events` table
- `backend/app/repositories/risk_repository.py` — create / query / stats
- `backend/app/services/risk_engine.py` — 5-rule evaluator (`evaluate()`)
- `backend/app/api/v1/risk.py` — `GET /risk`, `/risk/blocked`, `/risk/stats`

**Integration points:**
- `execution_engine.py` — changed `status == "PENDING"` → `status == "RISK_APPROVED"`
- `trade_decisions.status` lifecycle: `PENDING → RISK_APPROVED | BLOCKED → EXECUTED`
- `models/__init__.py` — added `RiskEvent`
- `api/v1/__init__.py` — added `risk_router`
- `core/database.py` — Layer 9 migration block
- `config/settings.py` — all 7 new risk settings

**Risk rules:**
| Rule | Check |
|------|-------|
| DUPLICATE_POSITION | OPEN position for same condition_id |
| MAX_OPEN_POSITIONS | Total OPEN ≥ MAX_OPEN_POSITIONS (10) |
| MAX_EXPOSURE | OPEN for this asset ≥ MAX_EXPOSURE_PER_ASSET (3) |
| DAILY_LOSS | Sum unrealized PnL ≤ MAX_DAILY_LOSS (−50.0) |
| DAILY_TRADES | Orders today ≥ MAX_DAILY_TRADES (20) |

---

## ✅ Refactor COMPLETE (2026-06-23)

**repositories/** — All 10 `*_repository.py` files moved from `services/` to `repositories/`.  
All imports updated via sed: `app.services.X_repository` → `app.repositories.X_repository`.

**workers/engine_workers.py** — All 9 background loop coroutines extracted from `main.py`.  
`main.py` now only contains lifespan + `create_application()`.

**schemas/** — 6 Pydantic schema files created. All API routers import from here instead of  
defining inline `class Foo(BaseModel)`.

---

## ⬜ Layer 10 — Portfolio Reporting (NEXT)

**Goal:** Aggregate performance metrics for the paper trading portfolio.

**Files to create:**
- `backend/app/api/v1/portfolio.py` — response endpoints
- `backend/app/repositories/portfolio_repository.py` — aggregate SQL queries
- `backend/app/schemas/portfolio.py` — Pydantic schemas

**Endpoints to implement:**
```
GET /api/v1/portfolio/summary     — total positions, PnL, win rate
GET /api/v1/portfolio/daily       — daily breakdown of fills and PnL
GET /api/v1/portfolio/by-asset    — performance split by BTC/ETH/SOL/XRP
GET /api/v1/portfolio/risk        — risk utilization (open vs max, loss vs limit)
```

**Key metrics:**
- `realized_pnl` — sum from CLOSED positions
- `unrealized_pnl` — sum from OPEN positions
- `win_rate` — closed positions where realized_pnl > 0 / total closed
- `avg_hold_duration` — avg (closed_at − opened_at) for CLOSED positions
- `risk_utilization_pct` — len(OPEN) / MAX_OPEN_POSITIONS × 100

**Estimated effort:** 2–3 hours

---

## ⬜ Position Close Logic (OPTIONAL)

Currently positions are OPEN indefinitely.  
Close trigger: when `market_universe.status` changes to `EXPIRED` for the position's condition_id.

**Change in `position_service.py`:**
1. Fetch all OPEN positions
2. For each: check `market_universe.status` for `condition_id`
3. If EXPIRED: set `status=CLOSED`, `close_price=current_price`, compute `realized_pnl`

**Estimated effort:** 1 hour

---

*Updated: 2026-06-23*
