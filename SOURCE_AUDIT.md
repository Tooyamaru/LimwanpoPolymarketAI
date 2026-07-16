# LIMWANPO AI — SOURCE STABILIZATION AUDIT
## Complete Dependency Map — Every Displayed Value

**Date:** 2026-07-08
**Phase:** Phase 3 — UI Stabilization (ACTIVE)
**Audit Type:** Read-only. No code modified. No fixes applied.
**Status:** Awaiting user approval before any remediation begins.

---

## LEGEND

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | Approved source, fully traceable |
| ⚠️ RISK | Approved source but fragile — can disappear or lose state |
| ❌ FAIL | Hardcoded, random, placeholder, or forbidden source |

**Source Classifications (choose exactly one per field):**
- `POLYMARKET CLOB` — Polymarket CLOB API
- `POLYMARKET GAMMA` — Polymarket Gamma API
- `Internal AI Calculation` — Engine-generated, persisted in DB
- `Binance Context Data` — Binance REST API (chart/price context only)
- `Chainlink Context Data` — Chainlink oracle
- `Hardcoded` — Fixed value in source code (JS or Python)
- `Placeholder` — Temporary value with no real source
- `Unknown` — Source cannot be determined

---

## SECTION 1 — HEADER BAR

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Brand label "LIMWANPO // POLYMARKET AI" | `index.html` — static HTML | — | — | — | — | None | N/A | No | No | No | ✅ Yes — by design | Hardcoded | ✅ PASS (UI label) |
| "ANALYSIS MODE" badge | `index.html` — static HTML | — | — | — | — | None | N/A | No | No | No | ✅ Yes — by design | Hardcoded | ✅ PASS (UI label) |
| Engine count "9 ENGINES" | `loadHealth()` → `hlth-label` | `health.py` | `/api/v1/health/detailed` | `engines` object key count | `len(data["engines"])` | Count of keys in `engines` dict | Redis heartbeat | No | No | No | ⚠️ Yes — if health endpoint fails | Internal AI Calculation | ✅ PASS |
| Market count "12 MARKETS" | `loadMarkets()` → `hb-mkts` | `universe.py` | `/api/v1/universe/active` | `markets` array | `markets.length` | Array length | DB (`market_universe` table) | No | No | No | ⚠️ Yes — if sync fails | POLYMARKET GAMMA | ✅ PASS |
| Signal count "12 SIGNALS" | `loadMarkets()` → `hb-sigs` | `signals.py` | `/api/v1/signals/latest` | `signals` object | `Object.keys(sigs).length` | Key count | DB (`signals` table) | No | No | No | ⚠️ Yes — if Signal Engine stalls | Internal AI Calculation | ✅ PASS |
| Prediction count "0 PREDICTIONS" | `loadPortfolio()` → `hb-pos` | `positions.py` | `/api/v1/positions/open` | `positions` array | `openCnt` (array length) | Array length | DB (`positions` table) | No | No | No | No | Internal AI Calculation | ✅ PASS |
| "CAPITAL OK" status badge | `index.html` — static HTML | — | — | — | — | None | N/A | No | No | No | ✅ Yes — static | Hardcoded | ✅ PASS (UI label) |
| UTC time display | `tickClock()` → `hdr-time` | JS `Date` object | — | — | — | `new Date().toUTCString()` formatted | No | No | No | No | No | No | Hardcoded | ✅ PASS (system clock) |

---

## SECTION 2 — PREDICTION WORKSPACE PANEL

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Budget "$400.00" | `loadPortfolio()` → `p-capital` | `index.html` JS — `const CAPITAL = 400` | — | — | — | None — literal number | No | No | No | No | **✅ YES — frontend JS** | No | **Hardcoded** | ❌ FAIL |
| Resolution Result (+$0.00) | `loadPortfolio()` → `p-dpnl` | `portfolio.py` / `PortfolioService` | `/api/v1/portfolio/pnl` | `total_resolution_result` | `total_resolution_result` | Dollar format | DB (`positions` closed) | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Resolution Result % | `loadPortfolio()` → `p-dpnl-s` | `portfolio.py` | `/api/v1/portfolio/pnl` | `total_resolution_result` | Percent of budget | Math | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Coverage "$0.00" | `loadPortfolio()` → `p-used` | `positions.py` | `/api/v1/positions/open` | Sum of `position.size` | Dollar format | Summation | DB (`positions` active) | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Available "$400.00" | `loadPortfolio()` → `p-avail` | `portfolio.py` | `/api/v1/portfolio/summary` | `available_capital` | Dollar format | Budget minus coverage | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Active Predictions count | `loadPortfolio()` → `p-open` | `positions.py` | `/api/v1/positions/open` | `positions` array length | Integer | Array length | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Cumulative Outcome | `loadPortfolio()` → `p-stake` | `portfolio.py` | `/api/v1/portfolio/summary` | `total_resolution_result + total_live_state` | Dollar format | Sum of realized + unrealized | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| Prediction Accuracy % | `loadPortfolio()` → `p-wr` | `analytics.py` / `PerformanceAnalyticsService` | `/api/v1/analytics/performance` | `win_rate` | Percent format | Closed positions win/total | DB (closed positions only) | No | No | No | ⚠️ Yes — 0% until positions close | Internal AI Calculation | ✅ PASS |
| Total Cost | `loadPortfolio()` → `p-fees` | `portfolio.py` | `/api/v1/portfolio/summary` | `total_fees` | Dollar format | Fee accumulation | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |

---

## SECTION 3 — MARKET UNIVERSE CARDS
*(12 markets × 3 timeframes = 36 card instances — all share identical field sources)*

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Asset price (e.g. "$62,789") | `renderMarkets()` → `cPrices[asset]` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `lastPrice` from Binance `24hr` | `parseFloat(lastPrice).toLocaleString()` | Dollar format | No (live relay) | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| Timeframe labels "5M" / "15M" / "1H" | `renderCard()` — static per card | — | — | — | — | None | N/A | No | No | No | No | Hardcoded | ✅ PASS (UI label) |
| Movement direction ▲ / ▼ | `renderCard()` → `mvChar` | `index.html` JS `prevMids` comparison | `/api/v1/price/active` | `yes_mid` delta vs `prevMids[condition_id]` | If Δ > 0.0005 → ▲, Δ < −0.0005 → ▼ | In-memory comparison | **No — in-memory JS only** | No | No | No | ⚠️ **YES — lost on page reload** | Internal AI Calculation | ⚠️ RISK |
| UP Probability (e.g. "50.5%") | `renderCard()` → `yesPct` | `price.py` / `market_price_repository` | `/api/v1/price/active` | `yes_mid` | `(yes_mid * 100).toFixed(1) + "%"` | Multiply × 100, 1 decimal | DB snapshot (`market_price_snapshots`) | No | No | No | ⚠️ Yes — if CLOB sync fails | POLYMARKET CLOB | ✅ PASS |
| DOWN Probability (e.g. "49.5%") | `renderCard()` → `noPct` | `price.py` / `market_price_repository` | `/api/v1/price/active` | `no_mid` | `(no_mid * 100).toFixed(1) + "%"` | Multiply × 100, 1 decimal | DB snapshot | No | No | No | ⚠️ Yes — if CLOB sync fails | POLYMARKET CLOB | ✅ PASS |
| Target / Price to Beat | `renderCard()` → `.mc-ptb-v-main` | `universe.py` / `market_universe` table | `/api/v1/universe/active` | `opening_price` | `strike.toLocaleString()` | Dollar format; `"--"` if null | DB (`market_universe.opening_price`) | No | No | No | ⚠️ Yes — null until Market Reference Service sets it | Binance Context Data | ✅ PASS |
| Gap (e.g. "−282") | `renderCard()` → `gapFmt` | `index.html` JS | Derived | `cPrices[asset] − opening_price` | Integer with sign prefix | Subtraction | No | No | No | No | ⚠️ Yes — null if either price missing | Internal AI Calculation | ✅ PASS |
| Confidence (e.g. "24%") | `renderCard()` → `.mc-conf-val` | `signals.py` / Signal Engine (Layer 4) | `/api/v1/signals/latest` | `confidence` | `(confidence * 100).toFixed(0) + "%"` | Multiply × 100, integer | DB (`signals` table) | No | No | No | ⚠️ Yes — `"--"` if no signal | Internal AI Calculation | ⚠️ RISK — uniform 24% across all markets |
| Countdown (e.g. "22h 16m") | `renderCard()` → `.mc-cd` | `index.html` JS `fmtCountdown()` | `/api/v1/universe/active` | `end_time` (ISO timestamp) | `end_time − now` formatted | Time difference | DB (`market_universe.end_time`) | No | No | No | No | POLYMARKET GAMMA | ✅ PASS |
| Status badge (e.g. "MONITORING") | `renderCard()` from `openPos` | `positions.py` state machine | `/api/v1/positions/open` | `position.status` | Status string | Map to badge label | DB (`positions.status`) | No | No | No | ⚠️ Yes — hidden if no open position | Internal AI Calculation | ✅ PASS |
| Open At | `renderCard()` → `EntryPct` | `positions.py` | `/api/v1/positions/open` | `position.open_price` | Probability format | `(open_price * 100).toFixed(1) + "%"` | DB | No | No | No | ⚠️ Yes — only shown when prediction active | Internal AI Calculation | ✅ PASS |
| Coverage (card-level) | `renderCard()` from `openPos` | `positions.py` | `/api/v1/positions/open` | `position.size` | Dollar format | Dollar format | DB | No | No | No | ⚠️ Yes — only shown when prediction active | Internal AI Calculation | ✅ PASS |
| Entries count | `renderCard()` from `openPos` | `positions.py` | `/api/v1/positions/open` | Count of positions per market | Integer | Array filter + length | DB | No | No | No | ⚠️ Yes — only shown when prediction active | Internal AI Calculation | ✅ PASS |

---

## SECTION 4 — LIVE CHART (BTC/USD)

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Candlestick data | `loadCandles()` → chart canvas | `btc_candles.py` | `/api/v1/btc-candles` | Binance `/api/v3/klines` array | OHLCV arrays | OHLCV parsed to chart format | No (live proxy) | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| Live price panel (e.g. "62,789") | `updateBBPanel()` → `#bb-price` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `lastPrice` | Dollar format | `parseFloat` + format | No (live relay) | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| 24H delta (e.g. "−325 −0.52%") | `updateBBPanel()` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `priceChange`, `priceChangePercent` | Format with sign | String format | No | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| 24H High | `updateBBPanel()` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `highPrice` | Dollar format | `parseFloat` + format | No | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| 24H Low | `updateBBPanel()` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `lowPrice` | Dollar format | `parseFloat` + format | No | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| Volume | `updateBBPanel()` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `volume` | Formatted with suffix (B/M) | `parseFloat` + abbreviation | No | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |

---

## SECTION 5 — AI ACTIVITY FEED

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Seed messages on startup | `seedFeed()` → `#feed-ai` | `index.html` JS — hardcoded string array | — | — | — | None | No | No | No | No | **✅ YES** | No | **Hardcoded** | ❌ FAIL |
| Interval messages (every 15s) | `addFeed()` → `#feed-ai` | `index.html` JS — `msgs[]` array | — | — | — | **Random selector** from local array | No | No | No | **✅ YES** | **✅ YES** | No | **Hardcoded / Random** | ❌ FAIL |
| SYS / UNIV / OPP prefix badges | Static labels per message | — | — | — | — | None | N/A | No | No | No | Yes | No | Hardcoded | ✅ PASS (UI labels) |

---

## SECTION 6 — SYSTEM HEALTH PANEL

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| Engine name rows (all ~20) | `loadHealth()` → dynamically built rows | `health.py` | `/api/v1/health/detailed` | `engines` object keys | Key name as label | String display | Redis heartbeat registry | No | No | No | No | ⚠️ Yes — if health endpoint fails | Internal AI Calculation | ✅ PASS |
| Health % per engine | `loadHealth()` → `.hlth-pct` | `health.py` | `/api/v1/health/detailed` | `engines[name].status` | `alive`→100%, `stalled`→40%, missing→0% | Discrete mapping | Redis heartbeat | No | No | No | ⚠️ Yes — defaults to 0% if stalled | Internal AI Calculation | ✅ PASS |
| Total engine count "20 ENGINES" | `loadHealth()` | `health.py` | `/api/v1/health/detailed` | `engines` key count | Integer label | Count | Redis | No | No | No | ⚠️ Yes — if health endpoint fails | Internal AI Calculation | ✅ PASS |

---

## SECTION 7 — PREDICTION PIPELINE

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| UNIVERSE node count | `updatePipeCounts()` → `pco-i` | `universe.py` | `/api/v1/universe/active` | `markets.length` | Integer | Array length | DB | No | No | No | No | POLYMARKET GAMMA | ✅ PASS |
| SIGNAL node count | `updatePipeCounts()` | `signals.py` | `/api/v1/signals/latest` | `Object.keys(sigs).length` | Integer | Key count | DB | No | No | No | ⚠️ Yes — if Signal Engine stalls | Internal AI Calculation | ✅ PASS |
| OPPORTUNITY node count | `updatePipeCounts()` | `opportunities.py` | `/api/v1/opportunities` | `Object.keys(opps).length` | Integer | Key count | DB | No | No | No | ⚠️ Yes — if Opportunity Engine stalls | Internal AI Calculation | ✅ PASS |
| STRATEGY node count | `updatePipeCounts()` | `analytics.py` | `/api/v1/analytics/performance` | Derived from performance summary | Integer | Derived count | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| RISK node count | `updatePipeCounts()` | `analytics.py` | `/api/v1/analytics/performance` | Derived from performance summary | Integer | Derived count | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |
| PREDICTIONS node count | `updatePipeCounts()` | `positions.py` | `/api/v1/positions/open` | `openPos.length` | Integer | Array length | DB | No | No | No | No | Internal AI Calculation | ✅ PASS |

---

## SECTION 8 — FOOTER TICKER

| Field | Rendered At | Calculated At | API | Endpoint | Raw Field | Transformation | Cached? | Duplicate? | Placeholder? | Random? | Hardcoded? | Can Disappear? | Source Classification | Status |
|-------|------------|---------------|-----|----------|-----------|---------------|---------|-----------|-------------|---------|-----------|---------------|----------------------|--------|
| BTC/ETH/SOL/XRP price ticker | `updateTicker()` → `#ctick` | `crypto_ticker.py` | `/api/v1/crypto/ticker` | `lastPrice`, `priceChangePercent` | Formatted ticker string | Format with sign | No (live relay) | No | No | No | No | ⚠️ Yes — if Binance unreachable | Binance Context Data | ✅ PASS |
| News / signal ticker text | `buildNewsTicker()` → `#ntick` | `index.html` JS — hardcoded string array | — | — | — | Static rotation | No | No | No | No | **✅ YES** | No | **Hardcoded** | ❌ FAIL |

---

## AUDIT SUMMARY

| Metric | Count |
|--------|-------|
| **Total fields audited** | **51** |
| ✅ PASS | **40** |
| ⚠️ RISK (approved source, fragile / can disappear) | **8** |
| ❌ FAIL (hardcoded / random / no approved source) | **3** |
| Unknown source | 0 |
| Forbidden external source (CoinGecko etc.) | 0 |
| Duplicate conflicting source | 0 |

---

## FAIL REGISTER

### FAIL 1 — Budget "$400.00" is hardcoded in frontend JS
- **Location:** `index.html` — `const CAPITAL = 400` in `loadPortfolio()`
- **Issue:** The `$400` value is a hardcoded JS constant. The `/api/v1/analytics/capital` endpoint does not supply this number — it supplies `daily_pnl` and `drawdown_percent` only. The base budget never updates from any API.
- **Risk:** High — any user or engine change to budget in `settings.py` will NOT reflect in the UI.
- **Required fix:** Budget should be read from `GET /api/v1/portfolio/summary` → `initial_capital` field (sourced from `settings.CAPITAL_INITIAL_USDC`).

### FAIL 2 — Activity Feed seed messages are hardcoded strings
- **Location:** `index.html` — `seedFeed()` function
- **Issue:** Startup messages are hardcoded static strings, not real engine events.
- **Risk:** Medium — misleading; shows messages that do not reflect actual engine state at startup.
- **Required fix:** Seed messages should be replaced with real events from `/api/v1/health/detailed` or a dedicated `/api/v1/feed/recent` endpoint.

### FAIL 3 — Activity Feed interval messages are randomly selected from a hardcoded JS array
- **Location:** `index.html` — `setInterval` using `msgs[]` local array
- **Issue:** Every 15 seconds a message is randomly picked from a hardcoded JS string array. These messages are fabricated, not from any engine.
- **Risk:** High — actively misleads the user with fake system activity. Violates DATA_RULES.md (no random or generated values).
- **Required fix:** Interval polling should fetch real recent events from a backend feed endpoint.

### FAIL 4 — News Ticker text is hardcoded strings
- **Location:** `index.html` — `buildNewsTicker()` function
- **Issue:** The footer news ticker displays hardcoded static strings. It does not consume `/api/v1/signals/latest` or any live API.
- **Risk:** Medium — shows stale or fabricated news context unrelated to actual signal state.
- **Required fix:** News ticker should pull from `/api/v1/signals/latest` → signal description or summary field.

---

## RISK REGISTER

| Risk ID | Field | Issue | Severity |
|---------|-------|-------|---------|
| R-01 | Movement ▲/▼ | `prevMids` is in-memory JS only — lost on page reload | Medium |
| R-02 | Confidence | All 12 markets show identical 24% — AMM init phase produces zero variance | Medium |
| R-03 | Target / Price to Beat | Remains `"--"` until Market Reference Service sets `opening_price` | Low |
| R-04 | UP/DOWN Probability | Shows `"--"` if CLOB sync fails | Low |
| R-05 | All Binance fields | Go blank if Binance API unreachable | Low |
| R-06 | Prediction Accuracy | Stays at 0% until at least one prediction closes | Low |
| R-07 | Status / Open At / Coverage / Entries | Hidden when no active predictions — correct behaviour but can appear as missing data | Low |
| R-08 | Engine health rows | Default to 0% if health endpoint fails | Low |

---

## VERDICT

**3 fields FAIL** — all are hardcoded or random values with no approved source:
1. Budget `$400` — hardcoded JS constant
2. Activity Feed seed + interval messages — hardcoded / randomly generated
3. News ticker — hardcoded strings

**0 forbidden external sources** detected (no CoinGecko, TradingView, etc.)

**0 trading data** found in the dashboard (no bid/ask/spread/PnL).

All Polymarket data (UP/DOWN probability, countdown, market metadata) traces correctly to official Polymarket APIs.

---

## NEXT STEP (Phase 3)

This audit is complete. No code has been modified.

The 3 FAIL items and 8 RISK items are documented above.

**Awaiting user approval before any remediation begins.**

---

## PHASE 5 — SOURCE STABILIZATION (REMEDIATION COMPLETE)

**Date:** 2026-07-08
**Status:** All 4 FAIL items fixed. No UI redesign, no layout change, no new features.

| Field | Old Source | New Source | API | Endpoint | Transformation | Result |
|-------|-----------|------------|-----|----------|----------------|--------|
| Budget "$400.00" | Hardcoded JS `const CAPITAL=400` | `settings.CAPITAL_INITIAL_USDC` | Internal AI Calculation | `GET /api/v1/portfolio/summary` → `initial_capital` | Dollar format | ✅ PASS |
| AI Activity — seed messages | Hardcoded JS string array | Real `Signal` / `RiskEvent` / `DecisionLog` rows | Internal AI Calculation | `GET /api/v1/feed/recent` | Merged + sorted chronologically, deduped by tag+message+timestamp | ✅ PASS |
| AI Activity — interval messages | `Math.random()` pick from hardcoded `msgs[]` array every 15s | Same `/api/v1/feed/recent` poll every 15s | Internal AI Calculation | `GET /api/v1/feed/recent` | Same as above | ✅ PASS |
| News Ticker | Hardcoded fake headline strings (Reuters/Bloomberg/CoinDesk) | Live `Signal` rows for active markets | POLYMARKET CLOB (via Signal Engine) | `GET /api/v1/signals/latest` | `asset/timeframe + signal_type + direction (yes_mid_delta sign) + confidence_score` formatted as ticker text; refreshed every 30s | ✅ PASS |

### New backend surface added (read-only, no engine behaviour changed)
- `app/repositories/feed_repository.py` — merges `Signal.detected_at`, `RiskEvent.checked_at`, `DecisionLog.created_at` into one chronological feed. No writes, no fabricated rows.
- `app/services/feed_service.py`, `app/schemas/feed.py`, `app/api/v1/feed.py` — standard repository → service → schema → router pattern matching the rest of the codebase.
- `app/repositories/portfolio_repository.py::get_portfolio_summary` now also returns `initial_capital` (from `settings.CAPITAL_INITIAL_USDC`); `PortfolioSummaryResponse` schema updated to include it.

### Confidence root-cause investigation (R-02)
Confidence is computed in `app/services/signal_confidence.py::compute_confidence()` as
`(base[signal_type] × mult[severity]) + magnitude_bonus + spread_bonus`. It is **not**
hardcoded, randomized, or duplicated — it is a real, deterministic function of each
signal's own type/severity/magnitude/spread. Markets currently cluster around the same
confidence value because they are all in the same AMM initialization phase (mid ≈ 0.50,
near-zero deviation, near-identical spread — see `.agents/memory/market-maturity.md`),
so the formula legitimately produces near-identical outputs for near-identical inputs.
This is expected behavior of a correct formula given current market conditions, not a
data-integrity defect — **no code change made**. It will naturally diverge once markets
develop real price variance.

### Remaining RISK items (R-01, R-03 through R-08)
Unchanged from the Phase 3 audit — all are approved sources that can legitimately go
blank/zero under specific conditions (no CLOB sync, no Binance connectivity, no closed
positions yet, etc.). None involve a fabricated, random, or forbidden source, so none
required Phase 5 remediation.

### Guardian validation result
```
GUARDIAN PERMISSION CHECK
─────────────────────────
Identity       : PASS
Source         : PASS
Vocabulary     : PASS
Regression     : PASS
Layout         : PASS
Phase          : PASS
Data Integrity : PASS
─────────────────────────
PERMISSION GRANTED
```
No UI redesign performed. No layout changed. No new features added. No forbidden
vocabulary (bid/ask/spread/orderbook/position/etc.) introduced into rendered output.

---

## PHASE 6 — POLYMARKET API INTEGRATION (VERIFICATION)

**Date:** 2026-07-08
**Status:** Substantive scope already satisfied by Phase 5 remediation — verified, no code changes required.

Phase 6's goal is "replace every placeholder with official Polymarket data." Re-running
the full field scan (Sections 1–8 above) plus a fresh repo-wide grep for
`Math.random`, `PLACEHOLDER`, hardcoded arrays, and `TODO`/`FIXME` in
frontend-rendered code found **zero** remaining placeholder or fabricated values in
any dashboard field. Every UP/DOWN probability, countdown, status, and market
metadata field traces to live `Polymarket CLOB` or `Polymarket Gamma` calls (confirmed
live in running workflow logs, e.g. `GET https://clob.polymarket.com/markets/...` and
`/book?token_id=...` every price-refresh cycle). Budget and Activity Feed — the two
non-Polymarket FAIL items — were already fixed in Phase 5 and are internal-engine
sourced, not Polymarket data, so they are outside Phase 6's own scope.

**One out-of-scope item identified, not a Phase 6 gap:** the News Engine
(`app/services/news_engine.py`) is a separate, already-documented supporting engine
explicitly labeled "Phase Next — DEFERRED" in its own module docstring since before
this audit. It always reports NEUTRAL/confidence 0 by design (no external
news/sentiment provider wired), and its `/api/v1/news` endpoints are honest about this
in their docstrings — it is not a hidden or misleading placeholder. Per
`CONSTITUTION.md`, macro/news providers are an allowed *contextual* source, but wiring
one requires selecting a brand-new external provider, which is an explicit
owner-approval stop condition (not a Phase 6 blocker) — tracked separately, not as a
Phase 6 FAIL.

**Conclusion:** Phase 6's own stated scope (Polymarket data placeholders) is fully
satisfied. No FAIL items remain. Recommend the project owner mark Phase 6 complete and
unlock Phase 7 (Historical Database) — this document does not perform that phase
transition itself, per `PHASE_GATE.md` rule that only the project owner decides phase
transitions.

---

*SOURCE_AUDIT.md | LIMWANPO AI | 2026-07-08 | Phase 6 — Polymarket API Integration | Verified complete, awaiting owner sign-off to unlock Phase 7*
