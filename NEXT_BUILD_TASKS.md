# NEXT BUILD TASKS

---

## ✅ Full Codebase Audit COMPLETE (2026-06-23)

**Scope:** All 90+ Python files across api/v1, models, repositories, services, workers, schemas, collector, core, config.

**Findings fixed:**

| Finding | Fix |
|---------|-----|
| 8 routers had inline Pydantic schemas | Created `schemas/market.py`, `schemas/price.py`, `schemas/scanner.py`, `schemas/discovery.py`, `schemas/classifier.py`, `schemas/universe.py`, `schemas/health.py`, `schemas/source_validation.py` — all routers now import from `schemas/` |
| `TradeDecision.status` docstring stale (old lifecycle) | Updated to `PENDING → RISK_APPROVED → EXECUTED` / `PENDING → BLOCKED` in both module docstring and column comment |
| `APP_VERSION` inconsistent (settings.py=0.6.0, .replit=0.6.0, docs=0.7.0) | Set to `0.9.0` everywhere: `settings.py`, env var override, `pyproject.toml`, all docs |
| `schemas/__init__.py` had no exports | Added full re-export of all 34 schema classes |
| `README.md` missing ~20 endpoints in API table | Full API table now documents all 48 endpoints |
| `PROJECT_STATUS.md` missing 28 endpoints, wrong version | Fully updated |

**Layers confirmed complete:** 1–9 (all 10 background loops running, 48 API endpoints, 14 schema files)

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

**workers/engine_workers.py** — All 9 background loop coroutines extracted from `main.py`.

**schemas/** — 14 Pydantic schema files (all domains covered, no inline schemas remain in routers).

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
