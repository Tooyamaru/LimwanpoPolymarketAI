---
name: BTC Chart Module frozen
description: Final production configuration and freeze policy for the BTC candlestick chart module
---

## Status
PRODUCTION READY — FROZEN as of 2026-06-29

## Frontend (backend/app/static/index.html)

| Aspect | Implementation |
|--------|---------------|
| Chart creation | `createChart()` called once per page load via `waitForChart()` → `initBtcChart()` |
| First load / TF change | `series.setData(candles)` + `btcChart.timeScale().fitContent()` + explicit resize |
| Realtime 30s ticks | `series.update(latest)` with `setData()` fallback on error |
| Stale-response guard | `btcFetchToken` monotonic counter; `myToken` captured before each `await`; checked at every async boundary including error paths |
| Loading overlay | `_showChartMsg('loading…')` before first fetch and on TF switch; `_clearChartMsg()` on every successful render |
| Error UI | HTTP error → `_showChartMsg('Data unavailable (HTTP N)')` after stale check; network error → `_showChartMsg('Connection error — retrying…')` after stale check |
| Data source | Only `/api/v1/btc/candles` — never direct Binance |
| ResizeObserver | 1 instance (`ro`) per page load; `btcChart.resize(w,h)` + `fitContent()` on every resize |
| Timer | `btcChartTimer` (30s `setInterval`); cleared before reset |
| TF switch | `updateBtcChartTf()` guards same-TF re-trigger; resets `btcDataLoaded=false` to force `setData` on next fetch |

## Backend (backend/app/api/v1/btc_candles.py)

| Aspect | Implementation |
|--------|---------------|
| Endpoint | `GET /api/v1/btc/candles?symbol&interval&limit` |
| Proxy target | `https://api.binance.com/api/v3/klines` |
| Interval validation | Allowlist of 16 valid Binance intervals |
| Timeout | `httpx.AsyncClient(timeout=15.0)` |
| Error mapping | 403→502, 429→502, 451→502, TimeoutException→504, ConnectError→502, HTTPStatusError→502 |
| HTTPException | Always re-raised via explicit `except HTTPException: raise` |
| Logging | Request start, Binance status+elapsed, candle count, all errors |

## Freeze policy
Modify ONLY if:
1. Reproducible bug
2. Runtime error
3. Security issue
4. Binance API change
5. Explicit user request

**Why:** Module reached production-ready state after full audit + 3 bug fixes (setData→update for realtime, network error UI, stale-response race). Further unsolicited changes risk regressions.
