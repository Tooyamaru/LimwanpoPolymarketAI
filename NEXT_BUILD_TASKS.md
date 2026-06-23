# NEXT BUILD TASKS

---

## ✅ Layer 6 — Strategy Engine SELESAI (2026-06-23)

**Files dibuat:**
- `backend/app/models/trade_decision.py` — Tabel `trade_decisions` (append-only log, bukan UPSERT)
- `backend/app/services/strategy_engine.py` — `StrategyEngine.run()`, rule-based decision
- `backend/app/services/trade_decision_repository.py` — insert + query functions
- `backend/app/api/v1/strategies.py` — 3 REST endpoints

**Decision rules:**
| Kondisi | Decision | skip_reason |
|---------|----------|-------------|
| spread_yes > 0.02 | SKIP | HIGH_SPREAD |
| direction == NEUTRAL | SKIP | NEUTRAL_DIRECTION |
| score ≥ 40 + BUY_NO | OPEN_LONG_NO | — |
| score ≥ 40 + BUY_YES | OPEN_LONG_YES | — |
| score 20–39 | WATCH | — |
| score < 20 | SKIP | LOW_SCORE |

**Konfigurasi ditambahkan ke settings.py:**
```
STRATEGY_ENGINE_ENABLED = True
STRATEGY_ENGINE_INTERVAL_SECONDS = 60
STRATEGY_ENGINE_RUN_ON_STARTUP = True
STRATEGY_PERSIST_SKIPS = False   # SKIP tidak disimpan ke DB agar tabel lean
```

**Background loop:** 60s, gated pada universe_ready event (sama seperti L4/L5)

**Verifikasi endpoints:**
```
GET /api/v1/strategies          — semua decisions (newest first)
GET /api/v1/strategies/active   — OPEN_LONG_YES/NO dengan status PENDING
GET /api/v1/strategies/stats    — aggregate counts + avg_score_actionable
```

---

## 🔴 Layer 7 — Execution Engine (BERIKUTNYA)

**Target:** Simulate order fills dari TradeDecision OPEN_LONG_* → Order record

**Files yang akan dibuat:**
- `backend/app/models/order.py` — tabel `orders` (paper mode)
- `backend/app/services/execution_engine.py` — paper simulator
- `backend/app/services/order_repository.py` — CRUD
- `backend/app/api/v1/orders.py` — monitoring endpoint

**Logic paper mode:**
- Baca OPEN_LONG_YES/NO decisions dengan status PENDING
- Simulate fill pada yes_ask (untuk YES) atau 1-yes_bid (untuk NO)
- Insert order record dengan status FILLED
- Update trade_decision status → EXECUTED

**Background loop:** 30s, gated universe_ready

*Updated: 2026-06-23*
