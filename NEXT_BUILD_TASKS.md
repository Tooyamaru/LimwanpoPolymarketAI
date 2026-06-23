# NEXT BUILD TASKS

---

## ✅ Layer 7 — Execution Engine SELESAI (2026-06-23)

**Files dibuat:**
- `backend/app/models/order.py` — Tabel `orders` (append-only fill log)
- `backend/app/services/execution_engine.py` — `ExecutionEngine.run()`, paper-mode simulator
- `backend/app/services/order_repository.py` — create + query functions
- `backend/app/api/v1/orders.py` — 4 REST endpoints

**Paper fill logic:**
| Decision | Side | fill_price |
|----------|------|------------|
| OPEN_LONG_YES | LONG_YES | yes_ask |
| OPEN_LONG_NO | LONG_NO | 1.0 - yes_bid |

**Alur eksekusi:**
1. Baca TradeDecision WHERE decision IN ('OPEN_LONG_YES','OPEN_LONG_NO') AND status='PENDING'
2. Hitung fill_price dari yes_ask / yes_bid (skip jika null)
3. Insert Order dengan status=FILLED
4. UPDATE TradeDecision SET status='EXECUTED'
5. commit()

**Konfigurasi ditambahkan ke settings.py:**
```
EXECUTION_ENGINE_ENABLED = True
EXECUTION_ENGINE_INTERVAL_SECONDS = 30
EXECUTION_ENGINE_RUN_ON_STARTUP = True
EXECUTION_PAPER_MODE = True
```

**Background loop:** 30s, gated pada universe_ready event

**Verifikasi startup log:**
```json
{"interval": 30, "paper_mode": true, "run_on_startup": true,
 "event": "Execution engine started"}
```

**Verifikasi endpoints:**
```
GET /api/v1/orders          → 200 []        (kosong — belum ada fills)
GET /api/v1/orders/open     → 200 []
GET /api/v1/orders/stats    → 200 {"total_orders":0,...}
GET /api/v1/orders/1        → 404           (expected)
```

---

## 🔴 Layer 8 — Position Tracking (BERIKUTNYA)

**Target:** Melacak posisi terbuka dari order fills, hitung P&L unrealized/realized.

**Files yang akan dibuat:**
- `backend/app/models/position.py` — tabel `positions`
  Fields: id, condition_id, asset, timeframe, side, size, entry_price,
          current_price, unrealized_pnl, realized_pnl, status, opened_at, closed_at
- `backend/app/services/position_service.py` — buka/tutup posisi dari order fills
- `backend/app/services/position_repository.py` — CRUD
- `backend/app/api/v1/positions.py` — endpoints

**Logic:**
- Buka posisi dari FILLED orders (status=OPEN)
- Update current_price dari price snapshots (setiap 30s)
- Hitung unrealized_pnl = (current_price - entry_price) × size
- Posisi ditutup manual atau saat market expire

**Background loop:** 30s

*Updated: 2026-06-23*
