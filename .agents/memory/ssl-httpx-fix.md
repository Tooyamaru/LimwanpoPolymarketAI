---
name: SSL httpx client fix — all services
description: Every httpx.AsyncClient() in the backend must use create_verified_httpx_client() from app.services.http_client or Polymarket/Binance calls fail with CERTIFICATE_VERIFY_FAILED in the Replit Nix environment.
---

## Rule
Never use bare `httpx.AsyncClient()` in this codebase. Always use `create_verified_httpx_client()` from `app.services.http_client`.

**Why:** Replit Nix: the default certifi CA path doesn't exist. The factory applies the system CA bundle (/etc/ssl/certs/ca-certificates.crt), fixing CERTIFICATE_VERIFY_FAILED for all external HTTPS calls (Polymarket CLOB, Gamma, Binance).

**How to apply:** Any new service making HTTP requests must import and use the factory. Files patched: clob_client.py, market_reference_service.py, binance_market_data.py (3 instances), btc_candles.py, crypto_ticker.py, gamma_series_client.py.

## Consequence of missing the fix
- CLOB: 0 price snapshots → 0 signals → 0 opportunities → 0 decisions (full pipeline dead)
- market_reference_service: opening_price = NULL for all active markets
- BTC chart: blank (btc_candles.py SSL fail)
- Crypto ticker: blank (crypto_ticker.py SSL fail)

## Condition_id staleness note
After a universe re-sync (e.g. on SSL fix restart), open positions in the DB will have OLD condition_ids that no longer match the current active markets. Dashboard correctly shows "—" for IN/OUT/PNL on current markets — this is expected, not a bug.

## hb-sigs race condition (fixed)
loadPortfolio() and loadMarkets() run concurrently in Promise.all(). hb-sigs badge must be updated inside loadMarkets() AFTER sigs is populated, not inside loadPortfolio() which races against sigs being filled.
