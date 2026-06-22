# ROADMAP — BUILD PHASE (Layers 6–10)

**Phase 1 (Research):** SELESAI — Audit #1–#5  
**Phase 2 (Build):** IN PROGRESS — Layer 5 baru selesai  
**Next target:** Layer 6 — Strategy Engine

---

## Layer 6 — Strategy Engine 🔴 PRIORITAS TERTINGGI BERIKUTNYA

**Tujuan:** Mengkonversi Opportunity Score + sinyal menjadi keputusan posisi terstruktur.

**Input:** `opportunities` table + `signals` table  
**Output:** `trade_decisions` table — BUY_YES | BUY_NO | HOLD | SKIP

**Decision logic (mean-reversion baseline dari audit findings):**
- Score ≥ 40 + direction=BUY_NO → open BUY_NO position
- Score ≥ 40 + direction=BUY_YES → open BUY_YES position
- Score 20–40 → watch (emit WATCH decision, no trade)
- Score < 20 → skip
- Market at NEUTRAL + score < 30 → skip

**Komponen:**
- `models/trade_decision.py` — tabel `trade_decisions`
- `services/strategy_engine.py` — rules evaluator
- `services/trade_decision_repository.py` — CRUD
- `api/v1/strategies.py` — endpoints
- Background loop: 30s (setelah opportunity engine)

**Estimasi:** 3–4 jam

---

## Layer 7 — Execution Engine 🟡 PRIORITAS 2

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

## Layer 8 — Position Tracking 🟠 PRIORITAS 3

**Tujuan:** Melacak posisi terbuka, P&L unrealized/realized.

**Komponen:**
- `models/position.py` — posisi (side, size, entry_price, current_price, pnl)
- `services/position_service.py` — update dari order fills
- `api/v1/positions.py`

**Estimasi:** 3–4 jam

---

## Layer 9 — Risk Engine 🟠 PRIORITAS 4

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

## Layer 10 — Monitoring Dashboard 🟢 PRIORITAS 5

**Minimum viable:**
- Live scores 12 markets
- Signal feed
- Active positions + P&L
- System health (loop latency, error rates)

**Estimasi:** 6–10 jam

---

## Timeline

| Layer | Estimasi | Dependency |
|-------|----------|------------|
| 6 Strategy Engine | 4 jam | L5 ✅ |
| 7 Execution Engine | 4 jam | L6 |
| 8 Position Tracking | 3 jam | L7 |
| 9 Risk Engine | 3 jam | L8 |
| 10 Dashboard | 8 jam | L3-L9 |
| **Total** | **~22 jam** | |

---

*Updated: 2026-06-22*
