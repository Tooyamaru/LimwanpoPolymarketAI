# ROADMAP — NEXT PHASE (Build Phase)

**Status riset:** SELESAI (Audit #1–#5)  
**Fase berikutnya:** BUILDING  
**Target:** Sistem yang menghasilkan sinyal dan dapat mengeksekusi posisi

---

## Layer 4 — Signal Engine 🔴 PRIORITAS TERTINGGI

**Tujuan:** Mendeteksi event harga yang bermakna dari stream `market_price_snapshots` dan menyimpannya sebagai sinyal terstruktur.

**Temuan audit yang relevan:**
- Mid bergerak di 1/12 pasar per 30 menit (jarang tapi nyata)
- Depth-drop batch terjadi sekitar 8–10 menit setelah market creation (LP scheduler)
- Tidak ada korelasi Binance — sinyal harus berbasis market internal, bukan spot

**Komponen yang dibangun:**
- `models/signal.py` — tabel `signals` (signal_type, asset, timeframe, mid_before, mid_after, delta, severity)
- `services/signal_engine.py` — scan 2 snapshot berturutan, deteksi perubahan
- `services/signal_repository.py` — DB operations untuk signals
- `api/v1/signals.py` — REST endpoint (GET /signals/latest, GET /signals/active)
- Integration ke `main.py` — background loop setelah price refresh
- `models/__init__.py` update — register Signal model

**Signal types:**
| Type | Kondisi | Severity |
|------|---------|----------|
| `MID_MOVE` | yes_mid berubah dari snapshot sebelumnya | LOW/MED/HIGH |
| `SEED_DEVIATION` | abs(yes_mid - 0.50) ≥ 0.01 | LOW/MED/HIGH |
| `SPREAD_CHANGE` | spread berubah ≥ 0.005 | LOW |

**Estimasi:** 4–6 jam

---

## Layer 5 — Strategy Engine 🟡 PRIORITAS 2

**Tujuan:** Mengkonversi sinyal menjadi keputusan posisi (BUY YES / BUY NO / HOLD) berdasarkan rules engine.

**Strategi berdasarkan audit:**
1. **Mean Reversion** — jika mid bergerak dari 0.50, bet kembali ke tengah
2. **Momentum** — jika mid sudah bergerak jauh dari seed, ikuti arah (rare)
3. **No-Trade Zone** — market dengan spread > 0.02 atau depth < threshold → skip

**Komponen:**
- `services/strategy_engine.py` — rules-based decision maker
- `models/trade_decision.py` — tabel keputusan (OPEN, HOLD, CLOSE)
- `api/v1/strategies.py` — endpoint untuk melihat keputusan aktif

**Estimasi:** 3–4 jam

---

## Layer 6 — Execution Engine 🟡 PRIORITAS 3

**Tujuan:** Mengirim order ke Polymarket CLOB (memerlukan autentikasi).

**Catatan penting:**
- CLOB `/trades` dan order submission memerlukan API key + wallet signing
- Perlu `py-clob-client` dari Polymarket
- Hanya dapat berjalan setelah autentikasi dikonfigurasi via secrets

**Komponen:**
- `services/execution_engine.py` — submit dan cancel orders
- `models/order.py` — tracking order CLOB
- `api/v1/orders.py` — endpoint monitoring

**Blocker:** Memerlukan Polymarket API key dan wallet. Bisa dibangun sebagai paper-trading mode dulu (simulasi tanpa actual order).

**Estimasi:** 6–8 jam (paper mode: 3 jam)

---

## Layer 7 — Position Tracking 🟠 PRIORITAS 4

**Tujuan:** Melacak posisi terbuka, P&L unrealized/realized, dan history transaksi.

**Komponen:**
- `models/position.py` — tabel posisi (kondisi, side, size, entry_price, current_price, pnl)
- `services/position_service.py` — update posisi dari order fills
- `api/v1/positions.py` — endpoint

**Estimasi:** 3–4 jam

---

## Layer 8 — Risk Engine 🟠 PRIORITAS 5

**Tujuan:** Mencegah kerugian besar. Max drawdown, position sizing, kill switch.

**Rules minimum:**
- Max position per market: configurable USDC limit
- Max concurrent open positions: 3
- Kill switch: if total loss > X%, stop all new orders
- Spread filter: skip market jika spread > 0.015

**Komponen:**
- `services/risk_engine.py` — pre-trade checks
- `models/risk_config.py` — parameter risk (configurable)
- `api/v1/risk.py` — override dan monitoring

**Estimasi:** 3–4 jam

---

## Layer 9 — Monitoring Dashboard 🟢 PRIORITAS 6

**Tujuan:** Web UI yang menampilkan status sistem, sinyal aktif, posisi, dan P&L.

**Pilihan implementasi:**
- Simple HTML dashboard di FastAPI (Jinja2 + vanilla JS)
- ATAU: API-first + simple React frontend

**Minimum viable dashboard:**
- Live price feed (12 markets)
- Signal feed (detected events)
- Active positions + P&L
- System health (loop status, error rates)

**Estimasi:** 6–10 jam

---

## Timeline Keseluruhan

| Layer | Modul | Estimasi | Dependency |
|-------|-------|----------|------------|
| 4 | Signal Engine | 5 jam | Layer 3 ✅ |
| 5 | Strategy Engine | 4 jam | Layer 4 |
| 6 | Execution Engine (paper) | 3 jam | Layer 5 |
| 7 | Position Tracking | 3 jam | Layer 6 |
| 8 | Risk Engine | 3 jam | Layer 7 |
| 9 | Dashboard | 8 jam | Layer 3-7 |
| **Total** | | **~26 jam** | |

---

*Generated: 2026-06-22*
