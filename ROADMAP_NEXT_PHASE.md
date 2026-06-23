# ROADMAP — BUILD PHASE (Layers 6–10)

**Phase 1 (Research):** SELESAI — Audit #1–#5  
**Phase 2 (Build):** IN PROGRESS — Layer 7 baru selesai  
**Next target:** Layer 8 — Position Tracking

---

## Layer 6 — Strategy Engine ✅ SELESAI (2026-06-23)

Decision rules: spread>0.02→SKIP | NEUTRAL→SKIP | score≥40→OPEN_LONG | 20–39→WATCH | <20→SKIP  
Background loop: 60s, gated universe_ready

---

## Layer 7 — Execution Engine ✅ SELESAI (2026-06-23)

Paper-mode fill: OPEN_LONG_YES→fill@yes_ask | OPEN_LONG_NO→fill@(1-yes_bid)  
Updates TradeDecision status → EXECUTED after fill.  
Background loop: 30s, gated universe_ready

---

## Layer 8 — Position Tracking 🔴 PRIORITAS TERTINGGI BERIKUTNYA

**Tujuan:** Melacak posisi terbuka, P&L unrealized/realized dari order fills.

**Komponen:**
- `models/position.py` — posisi (side, size, entry_price, current_price, pnl)
- `services/position_service.py` — buka dari fills, update harga, hitung P&L
- `services/position_repository.py` — CRUD
- `api/v1/positions.py` — endpoints

**Estimasi:** 3–4 jam

---

## Layer 9 — Risk Engine 🟠 PRIORITAS 2

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

## Layer 10 — Monitoring Dashboard 🟢 PRIORITAS 3

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
| 7 Execution Engine | ✅ SELESAI | — | L6 ✅ |
| 8 Position Tracking | 🔴 NEXT | 3 jam | L7 ✅ |
| 9 Risk Engine | 🟠 | 3 jam | L8 |
| 10 Dashboard | 🟢 | 8 jam | L3-L9 |
| **Total remaining** | | **~14 jam** | |

---

*Updated: 2026-06-23*
