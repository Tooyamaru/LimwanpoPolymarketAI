# ROADMAP — NEXT PHASE (Layer 10+)

**Phase 1 (Research):** COMPLETE — Audit, source validation  
**Phase 2 (Build):** COMPLETE — Layers 1–9 all live  
**Phase 3 (Reporting):** COMPLETE — Layer 10 Portfolio Reporting live  
**Next target:** Layer 11 — Live Trading

---

## ✅ Layer 1 — Market Collector (COMPLETE)
Binance Spot + Polymarket page collector, 5s tick.

## ✅ Layer 2 — Scanner (COMPLETE)
Full scan ~20k Polymarket markets, UPDOWN classifier, event types.

## ✅ Layer 3 — Universe Sync + Price Refresh (COMPLETE)
12 known series synced via Gamma Events API. CLOB bid/ask every 10s.

## ✅ Layer 4 — Signal Engine (COMPLETE)
MID_MOVE, SPREAD_COMPRESSION, SEED_DEVIATION detection every 10s.

## ✅ Layer 5 — Opportunity Engine (COMPLETE)
Composite score 0–100 with 5 weighted components. Upsert every 30s.

## ✅ Layer 6 — Strategy Engine (COMPLETE)
Score ≥ 40 → OPEN_LONG_YES/NO. Watch 20–39. Skip < 20 or spread > 0.02.

## ✅ Layer 7 — Execution Engine (COMPLETE, Paper Mode)
Instant paper fills at CLOB best ask. No slippage. RISK_APPROVED only.

## ✅ Layer 8 — Position Tracking (COMPLETE)
Open positions from fills. Live unrealized PnL updated every 30s.

## ✅ Layer 9 — Risk Engine (COMPLETE — 2026-06-23)
5 portfolio risk rules gate PENDING decisions before execution.
PENDING → RISK_APPROVED | BLOCKED.

---

## ✅ Layer 10 — Portfolio Reporting (COMPLETE — 2026-06-23)

**Goal:** Aggregate performance metrics for the paper trading portfolio.

**Files created:**
- `repositories/portfolio_repository.py` — 5 read-only aggregate queries
- `services/portfolio_service.py` — PortfolioService assembles responses
- `schemas/portfolio.py` — 5 Pydantic response schemas
- `api/v1/portfolio.py` — 5 read-only GET endpoints

**Endpoints live:**
- `GET /api/v1/portfolio/summary` — positions + orders + decisions overview
- `GET /api/v1/portfolio/positions` — breakdown by status / asset / side
- `GET /api/v1/portfolio/orders` — breakdown by status / asset / side
- `GET /api/v1/portfolio/risk` — allowed/blocked counts + by-reason
- `GET /api/v1/portfolio/pnl` — unrealized (OPEN) + realized (CLOSED) PnL

**Tests:** `test_portfolio_repository.py`, `test_portfolio_service.py`, `test_portfolio_api.py`

---

## ⬜ Layer 11 — Live Trading (NEXT)

**Goal:** Replace paper-mode fills with real CLOB order submission.

**Requirements:**
- Polymarket API key + wallet
- CLOB order submission via `POST /order` with ECDSA signature
- Order state polling (OPEN → MATCHED → FILLED)
- Real position tracking against actual CLOB fills
- Risk Engine tightened for real-money exposure

**Estimated effort:** 6–8 hours

---

## ⬜ Layer 12 — Backtesting Engine (FUTURE)

**Goal:** Replay strategy against historical price snapshots in DB.

**Components:**
- Replay engine: iterate over `market_price_snapshots` by time window
- Virtual signal + opportunity engine (in-memory, no DB writes)
- P&L curve output
- Comparison: paper strategy vs. baseline (always BUY_YES)

**Estimated effort:** 4–6 hours

---

## ⬜ Layer 13 — Alert System (FUTURE)

**Goal:** Push notifications for high-priority signals and fills.

**Options:**
- Webhook (Discord, Slack)
- Email (SendGrid)
- Trigger: signal severity=HIGH, RISK_APPROVED fill, BLOCKED decision

**Estimated effort:** 2–3 hours

---

## Timeline

| Layer | Status | Est. Effort |
|-------|--------|-------------|
| 10 Portfolio Reporting | ✅ COMPLETE | 2–3 hrs |
| 11 Live Trading | ⬜ NEXT | 6–8 hrs |
| 12 Backtesting | ⬜ FUTURE | 4–6 hrs |
| 13 Alert System | ⬜ FUTURE | 2–3 hrs |
| **Total remaining** | | **~18 hrs** |

---

*Updated: 2026-06-23*
