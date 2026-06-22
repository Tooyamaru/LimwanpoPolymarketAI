# NEXT BUILD TASKS

---

## ✅ Layer 5 — Opportunity Engine SELESAI (2026-06-22)

**Files dibuat:**
- `backend/app/models/opportunity.py` — Tabel `opportunities` dengan 5 score columns + UPSERT via ON CONFLICT
- `backend/app/services/opportunity_engine.py` — `OpportunityEngine.evaluate()`, 5 sub-score functions
- `backend/app/services/opportunity_repository.py` — upsert + query functions
- `backend/app/api/v1/opportunities.py` — 4 REST endpoints

**Score components:**
| Component | Max | Formula |
|-----------|-----|---------|
| mid_movement | 30 | min(30, abs(mid - 0.50) × 600) |
| spread | 20 | max(0, (0.02 - spread) × 2000) |
| depth_imbalance | 20 | min(20, abs(spread_no - spread_yes) × 2000) |
| signal_activity | 20 | 0→10→15→20 pts by count; +3 per HIGH |
| discovery | 10 | time-to-expiry urgency tiers |

**Bug ditemukan dan fixed:**
- `universe_ready` asyncio.Event ter-block forever ketika `UNIVERSE_SYNC_RUN_ON_STARTUP=false` (Replit env var)
- Fix: set event immediately di else-branch dari startup check di `_run_universe_sync_loop`

**Verifikasi (2026-06-22):**
```
GET /api/v1/opportunities/stats
{"total_markets": 12, "avg_score": 18.0, "top_score": 44.0, "top_asset": "SOL"}

Top 5:
  SOL/5m  → 44.0  BUY_NO  (mid=0.705, anomalous snapshot)
  XRP/5m  → 24.0  NEUTRAL (mid=0.505, tight spread)
  XRP/15m → 24.0  NEUTRAL
  BTC/1H  →  1.0  NEUTRAL (seed, wide spread)
```

---

## 🔴 Layer 6 — Strategy Engine (BERIKUTNYA)

**Target:** Konversi Opportunity Score → TradeDecision

**Files yang akan dibuat:**
- `backend/app/models/trade_decision.py`
- `backend/app/services/strategy_engine.py`
- `backend/app/services/trade_decision_repository.py`
- `backend/app/api/v1/strategies.py`

**Decision rules (mean-reversion):**
- Score ≥ 40, direction = BUY_NO → OPEN_LONG_NO
- Score ≥ 40, direction = BUY_YES → OPEN_LONG_YES
- Score 20–39 → WATCH
- Score < 20 → SKIP
- Spread > 0.02 → SKIP (terlalu mahal)

**Background loop:** 30s, gated pada universe_ready

*Updated: 2026-06-22*
