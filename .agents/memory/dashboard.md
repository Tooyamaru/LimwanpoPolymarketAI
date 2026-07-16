---
name: Cyberpunk dashboard
description: Fullscreen cyberpunk trading dashboard served as FastAPI static file
---

# Dashboard setup

**File**: `backend/app/static/index.html` — single self-contained HTML/CSS/JS, no build step.
**Current version**: V12.4 (UI FREEZE FINAL — poly-id subtitle removed from header; WAITING FOR SCANNER small text via scanner-wait CSS class (guarded in all 5 responsive breakpoints); TOP 3 shows Waiting...; positions panel sentence-case text, font raised; Last Closed circle removed → "No trades yet"; generateFeed neutral messages only)

**FastAPI mount** (in `create_application()` in `main.py`):
```python
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/static/index.html")
```
Working directory when uvicorn runs is `backend/`, so `Path(__file__).parent` resolves to `backend/app/`.

# API endpoints used

| Endpoint | Dashboard use |
|---|---|
| `/api/v1/price/active` | 4-asset cards + heatmap (asset, tf, yes_mid) |
| `/api/v1/opportunities` | joined by condition_id for score + direction |
| `/api/v1/positions/open` | active positions panel |
| `/api/v1/orders/stats` | pipeline EXEC count |
| `/api/v1/strategies/stats` | pipeline STRATEGY count |
| `/api/v1/analytics/performance` | KPI cards (win rate, pnl, trades, drawdown) |
| `/api/v1/analytics/capital` | capital protection bars |
| `/api/v1/health` | uptime display |
| `/api/v1/signals/stats` | pipeline SIGNALS count |
| `/api/v1/risk/stats` | pipeline RISK count |

# Layout — V7.0

- **Header** (42px): logo, PAPER MODE, 9 ENGINES LIVE, 4 ASSETS · SIGNALS · OPEN · BLOCKED, CAPITAL OK, uptime, clock
- **Left col** (22%): "4 ASSETS MONITORED" panel with 4 asset cards (BTC/ETH/SOL/XRP); each card shows icon, best score across TFs, best direction badge, best TF chip, best mid odds
- **Center col** (56%):
  - `#center-top-row` grid (1fr 250px): `#target-panel` + `#btc-chart-card` (TradingView mini symbol overview widget)
  - `#pipeline-panel`: UNIVERSE (4) → SIGNALS → OPPS → STRATEGY → RISK → EXECUTION
  - `#heatmap-panel`: 4×3 grid heatmap
- **Right col** (22%): POSITIONS + SYSTEM HEALTH
- **Bottom** (`#perf-section`): 8 KPI cards + bot-row (AI Thinking Feed | AI Live Feed | Capital Protection)
- **Footer** (22px): LIMWANPO // POLYMARKET AI | BTC · ETH · SOL · XRP · 5M | 15M | 1H · PAPER MODE | timestamp

# Key JS functions

- `buildMarketList()` — builds 4 asset cards in `#mkt-list` (ids: `ac-{A}`, `acs-{A}`, `acd-{A}`, `actf-{A}`, `aco-{A}`)
- `updateAssetCards()` — called each refresh; picks best score/dir/mid across TFs from `mktData` for each asset
- `updateMarketRow(asset,tf,score,dir,mid)` — still called per-market-price but silently returns (no DOM rows); data lands in `mktData` for updateAssetCards to consume
- `updateLiveStatus(ranked,posOpen,blocked)` — updates header pill: lm-active always = ASSETS.length (4)
- `updatePipeline(...)` — UNIVERSE stage shows `ASSETS.length` (4), not BASE(12)

# CSS architecture additions (V7.0)

- `.asset-card`, `.ac-*` — 4-asset left sidebar card styles
- `#center-top-row` — CSS grid `1fr 250px`, flex-shrink:0; collapses to 1fr on portrait
- `#btc-chart-card` — flex column, hidden on portrait via media query
- `#left-feed-panel{display:none!important}` — removed from HTML and hidden via CSS

# Portrait breakpoints

- `#center-top-row{grid-template-columns:1fr!important;} #btc-chart-card{display:none!important;}` in portrait MQ
- Left col rendered as col:nth-child(1) order:2 (below center/hero in portrait)
