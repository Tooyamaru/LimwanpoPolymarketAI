# NEXT BUILD TASKS — Signal Engine (Layer 4)

**Status: ✅ SELESAI — 2026-06-22**

---

## Task 1: Model `signals` ✅ SELESAI
File: `backend/app/models/signal.py`
- Tabel `signals` terbuat di PostgreSQL
- 10 index: condition_id, asset, timeframe, signal_type, severity, detected_at, compound indexes
- Kolom: signal_type, yes_mid_before/after/delta, spread_before/after/delta, seed_deviation, severity, snapshot FKs

## Task 2: Signal Repository ✅ SELESAI
File: `backend/app/services/signal_repository.py`
- `save_signal()` — insert signal baru
- `get_latest_signals(limit)` — semua market
- `get_signals_by_market(condition_id, limit)` — per market
- `get_active_market_signals(limit)` — hanya market aktif
- `get_signal_count()` — total count
- `get_signal_counts_by_type()` — breakdown per type
- `get_signal_counts_by_severity()` — breakdown per severity
- `get_last_signal_for_market(condition_id, type)` — untuk deduplication

## Task 3: Signal Engine Service ✅ SELESAI
File: `backend/app/services/signal_engine.py`
- `SignalEngine.scan(session)` — scan semua market aktif
- Deteksi MID_MOVE (threshold: >0.001 delta)
- Deteksi SEED_DEVIATION (threshold: |mid - 0.50| ≥ 0.01)
- Deteksi SPREAD_CHANGE (threshold: |spread_delta| ≥ 0.005)
- Severity tiers: LOW/MEDIUM/HIGH berdasarkan magnitude
- Deduplication: skip jika sinyal identik dengan sinyal terakhir

## Task 4: API Endpoint `/signals` ✅ SELESAI
File: `backend/app/api/v1/signals.py`
- `GET /api/v1/signals/latest?limit=50`
- `GET /api/v1/signals/active?limit=50`
- `GET /api/v1/signals/stats`
- `GET /api/v1/signals/{condition_id}?limit=20`

## Task 5: Integration ke `main.py` ✅ SELESAI
- `_run_signal_engine_loop()` — background loop setiap 10s
- Gates pada `universe_ready` event (tidak jalan sebelum sync pertama)
- Graceful shutdown: signal_task di-cancel bersama task lain

## Task 6: Register Model & Router ✅ SELESAI
- `models/__init__.py` — Signal terdaftar
- `api/v1/__init__.py` — signals_router terdaftar
- `config/settings.py` — SIGNAL_ENGINE_ENABLED/INTERVAL/RUN_ON_STARTUP
- `APP_VERSION` bumped ke 0.5.0

---

## Verifikasi (2026-06-22)

```
GET /api/v1/signals/stats
{"total_signals": 0, "by_type": {}, "by_severity": {}}
```

Zero sinyal = BENAR. Semua pasar masih di 0.50–0.505 (dev maks 0.005 < threshold 0.01).
Konsisten dengan temuan Audit #5: pure AMM init phase, tidak ada aktivitas trading manusia.

Signal Engine akan mulai emit sinyal begitu ada market yang bergerak > 1% dari seed.

---

## LAYER 5 — Strategy Engine (BERIKUTNYA)

Input: `signals` table  
Output: `trade_decisions` table — BUY_YES | BUY_NO | HOLD  
Rules awal: Mean-reversion terhadap seed 0.50  

Files yang akan dibuat:
- `backend/app/models/trade_decision.py`
- `backend/app/services/strategy_engine.py`
- `backend/app/services/trade_decision_repository.py`
- `backend/app/api/v1/strategies.py`

*Generated: 2026-06-22*
