---
name: Cyberpunk dashboard
description: Fullscreen cyberpunk trading dashboard served as FastAPI static file
---

# Dashboard setup

**File**: `backend/app/static/index.html` — single self-contained HTML/CSS/JS, no build step.

**FastAPI mount** (in `create_application()` in `main.py`):
```python
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/static/index.html")
```
Working directory when uvicorn runs is `backend/`, so `Path(__file__).parent` resolves to `backend/app/`.

**Why Path(__file__).parent:** Using a relative string like `"app/static"` would break if cwd changes; the absolute path from `__file__` is always correct.

# API endpoints used

| Endpoint | Dashboard use |
|---|---|
| `/api/v1/price/active` | 12 market cells (asset, tf, yes_mid) |
| `/api/v1/opportunities` | joined by condition_id for score + direction |
| `/api/v1/positions/open` | active positions panel |
| `/api/v1/positions/stats` | pipeline OPEN + CLOSED counts |
| `/api/v1/orders/stats` | pipeline EXEC count |
| `/api/v1/strategies/stats` | pipeline STRATEGY count |
| `/api/v1/analytics/performance` | KPI cards (win rate, pnl, trades, drawdown) |
| `/api/v1/analytics/capital` | capital protection bars |
| `/api/v1/health` | uptime display |
| `/api/v1/signals/stats` | pipeline SIGNALS count |
| `/api/v1/risk/stats` | pipeline RISK count |

# Layout

- Header (44px): logo, capital dot, uptime, UTC clock
- Left col (272px): 4 asset groups × 3 timeframe market cells
- Center col (1fr): canvas pipeline animation (top) + KPI cards + capital bars (bottom)
- Right col (252px): open positions list + system health engine grid
- Footer (28px): version, last-refresh timestamp, market count

# Pipeline nodes (left → right)
SIGNALS → OPPS → STRATEGY → RISK → EXEC → OPEN → CLOSED → PNL

Animated with canvas particle system; nodes glow cyan/green/magenta when count > 0.
