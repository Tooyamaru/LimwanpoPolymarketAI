---
name: Asset header live prices
description: Architecture decision for live BTC/ETH/SOL/XRP prices in column headers
---

## Rule
Header prices use a **Binance MiniTicker WebSocket** (combined stream), not REST polling.
The WS patches only `.asset-live-px[data-asset]` spans — no Market Universe DOM rebuild.
`fetchPrices()` (REST `/api/v1/crypto/ticker`) is kept at 30s for supplementary BTC chart 24h data and footer ticker.

**Why:**
REST polling every 1-5s caused unnecessary load and latency. WS push is genuinely real-time with near-zero CPU overhead.

## How to apply
- Combined stream URL: `wss://stream.binance.com:9443/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker/solusdt@miniTicker/xrpusdt@miniTicker`
- `_AMAP` maps Binance symbol → asset key (`btcusdt→BTC` etc.)
- On message: update `cPrices[asset]` (price/pct/high/low/vol), then querySelector the matching span and set `textContent`
- Footer ticker rebuild is debounced 80ms (4 assets arrive in rapid succession)
- Auto-reconnect: exponential backoff 3s→6s→…30s max; single timer guard; `_priceWsClosing` flag prevents reconnect on intentional close (beforeunload)

## Edit rule
The `data-asset` attribute on the header span MUST be set in the `renderMarkets()` template literal. Edit tool CANNOT safely edit lines inside JS template literals — use Python script instead.
