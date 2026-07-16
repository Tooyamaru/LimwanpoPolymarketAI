---
name: Frontend performance optimizations
description: 8-phase audit and implementation of all real performance optimizations for the LIMWANPO dashboard frontend and backend.
---

## Optimizations implemented

### Frontend (index.html)

**1. flowEnergy CSS animation — left → transform:translateX**
- Original used `left:-35%` to `left:115%` (layout-triggering, forces reflow every frame at 60fps for 15 animated elements).
- Replaced with `transform:translateX(-117%)` to `transform:translateX(383%)`.
- Math: element width=30% of parent. translateX is % of element's own width. `-117% × 0.30 = -35%` parent. `383% × 0.30 = 115%` parent. ✅
- Flow particle elements must have `left:0` as a fixed inline style so translateX is relative to the left edge. Added to buildPipeline HTML.

**2. animatePipe — delta-only updates**
- Old: all 6 nodes rewritten every 2800ms (~70 style operations).
- New: tracks `prevIdx`, only updates 2 changed nodes (deactivate prev, activate curr).
- Connector updates scoped to Set of 4 affected connector indices (prevIdx-1, prevIdx, idx-1, idx).
- `.dot` element cached in `_pipeDot` module variable (no querySelector on every tick).

**3. buildNewsTicker — eliminated duplicate API fetch**
- Was calling `/api/v1/signals/latest?limit=12` every 30s independently of `loadMarkets`.
- Converted to synchronous function using `Object.values(sigs)` (already loaded by loadMarkets).
- Removed standalone `setInterval(()=>buildNewsTicker(),30000)`.
- Now called from `refresh()` after `loadMarkets()` resolves, so sigs is always current.
- Net: **1 fewer API call per 30s cycle** (saves 1 DB query + network round-trip).

**4. Countdown timer — cached element array**
- Was: `querySelectorAll(".mc-cd[data-end]")` every 1s → DOM traversal on every second.
- Now: `_cdEls = []` array, refreshed by `refreshCdCache()` called at end of `renderMarkets()`.
- Countdown setInterval iterates `_cdEls` directly.

**5. fetchPrices deduplication**
- 15s standalone interval + 30s refresh both call fetchPrices.
- At 60s mark both fire simultaneously (60 is multiple of both 15 and 30).
- Added `_lastPriceFetchTs` guard: skip if called within 10s. First call always goes through.

**6. backdrop-filter removed from #bb-panel**
- `backdrop-filter:blur(6px)` was creating a GPU compositing layer unnecessarily.
- Panel has `background:rgba(2,4,9,.98)` — effectively opaque — so blur was invisible.
- Removed.

**7. Dead code removed**
- `fmtAge()` function defined but never called → removed.
- `totalPnl` and `totalEquity` variables computed in loadPortfolio but never read → removed.

### Backend (health.py)

**8. /health/detailed — 20s in-memory cache**
- Endpoint runs 6+ DB queries per call (2 service evaluations + 4 MAX() aggregates + 2 more).
- Dashboard polls every 30s; multiple open tabs or monitoring tools cause bursts.
- Added module-level `_health_cache = {"ts": 0.0, "data": None}` with `_HEALTH_CACHE_TTL = 20.0`.
- Cache is per-process (not shared across uvicorn workers) — benign: at most 1 duplicate query per worker on cache miss.

## Why: CSS `left` vs `transform` matters
`left` property animation triggers layout recalculation every frame (60fps) for every animated element. `transform` runs on the GPU compositor thread with no layout impact. For 15 animated flow particles (5 connectors × 3 particles each), this is a significant CPU/GPU saving.

## Corruption warning
The HTML edit corruption issue (MEMORY: html-edit-corruption.md) was triggered during this session when editing a line containing single-quoted strings inside a JS template literal. The Edit tool split the line at the single-quote boundary. Recovery required Python script to restore the full line. Always use Python for lines with `'<span...>'` inside template literals.
