# ROADMAP — BUILD PHASE (Layers 6–10)

**Phase 1 (Research):** SELESAI — Audit #1–#5  
**Phase 2 (Build):** IN PROGRESS — Layer 6 baru selesai  
**Next target:** Layer 7 — Execution Engine

---

## Layer 6 — Strategy Engine ✅ SELESAI (2026-06-23)

**Input:** `opportunities` table  
**Output:** `trade_decisions` table — OPEN_LONG_YES | OPEN_LONG_NO | WATCH | SKIP

**Decision logic:**
- spread_yes > 0.02 → SKIP (HIGH_SPREAD)
- direction == NEUTRAL → SKIP (NEUTRAL_DIRECTION)
- score ≥ 40 + BUY_NO → OPEN_LONG_NO
- score ≥ 40 + BUY_YES → OPEN_LONG_YES
- score 20–39 → WATCH
- score < 20 → SKIP (LOW_SCORE)

**Background loop:** 60s, gated pada universe_ready

---

## Layer 7 — Execution Engine 🔴 PRIORITAS TERTINGGI BERIKUTNYA

**Tujuan:** Mengirim order ke Polymarket CLOB (paper mode dulu).

**Catatan:**
- Order submission memerlukan API key + wallet signing (py-clob-client)
- Paper mode: simulate fills tanpa actual order ke CLOB
- Real mode: akan diaktifkan setelah risk engine selesai

**Komponen:**
- `services/execution_engine.py` — paper order simulator
- `models/order.py` — order tracking
- `api/v1/orders.py` — monitoring endpoint

**Estimasi:** 3–4 jam (paper mode)

---

## Layer 8 — Position Tracking 🟠 PRIORITAS 2

**Tujuan:** Melacak posisi terbuka, P&L unrealized/realized.

**Komponen:**
- `models/position.py` — posisi (side, size, entry_price, current_price, pnl)
- `services/position_service.py` — update dari order fills
- `api/v1/positions.py`

**Estimasi:** 3–4 jam

---

## Layer 9 — Risk Engine 🟠 PRIORITAS 3

**Rules minimum:**
- Max posisi per market: configurable USDC limit
- Max concurrent open positions: 3
- Kill switch: total loss > X%
- Spread filter: skip jika spread > 0.015

**Komponen:**
- `services/risk_engine.py` — pre-trade checks
- `models/risk_config.py`
- `api/v1/risk.py`

**Estimasi:** 3–4 jam

---

## Layer 10 — Monitoring Dashboard 🟢 PRIORITAS 4

**Minimum viable:**
- Live scores 12 markets
- Signal feed
- Active positions + P&L
- System health (loop latency, error rates)

**Estimasi:** 6–10 jam

---

## Timeline

| Layer | Status | Estimasi | Dependency |
|-------|--------|----------|------------|
| 6 Strategy Engine | ✅ SELESAI | — | L5 ✅ |
| 7 Execution Engine | 🔴 NEXT | 4 jam | L6 ✅ |
| 8 Position Tracking | 🟠 | 3 jam | L7 |
| 9 Risk Engine | 🟠 | 3 jam | L8 |
| 10 Dashboard | 🟢 | 8 jam | L3-L9 |
| **Total remaining** | | **~18 jam** | |

---

*Updated: 2026-06-23*
