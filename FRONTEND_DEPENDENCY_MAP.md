# LIMWANPO AI — FRONTEND DEPENDENCY MAP
**Date:** 2026-07-07  
**Source:** `backend/app/static/index.html` — only `fetch()` calls counted.  
**Method:** Every fetch() call in the JS was identified by hand from the actual source file.  
No assumptions. No router listing. Only confirmed fetch() calls are classified FE.

---

## Classification Key

| Code | Meaning |
|---|---|
| **FE** | Called by actual `fetch()` in `index.html` |
| **UNU** | Endpoint exists in the backend but no `fetch()` call in `index.html` |
| **INT** | Internal backend call (service-to-service, no HTTP) |

---

## CONFIRMED FRONTEND FETCH() CALLS

### 1. GET `/api/v1/btc/candles`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadCandles(tf)` |
| **Query params** | `interval={tf}` (5m / 15m / 1h), `limit=80` |
| **Called from** | `init()` on startup, `switchTF()` on tab click, `setInterval` every 60 s |
| **Usage** | Populates the LightweightCharts candlestick series in `#chart-panel` (Row 1 centre). Also updates `#bb-price`, `#bb-d1`, `#bb-d2`, `#bb-24h`, `#bb-24l`, `#bb-vol`, `cPrices.BTC`. |
| **Router file** | `btc_candles.py` — proxies Binance `/api/v3/klines` |

---

### 2. GET `/api/v1/crypto/ticker`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `fetchPrices()` |
| **Called from** | `refresh()` (every 30 s) + `setInterval` every 15 s |
| **Usage** | Populates `cPrices{}` map (BTC/ETH/SOL/XRP/BNB). Drives: crypto ticker strip (`#ctick`), `#bb-price` live update, `.asset-live-px` labels in every market column header. |
| **Router file** | `crypto_ticker.py` — proxies Binance `/api/v3/ticker/24hr` |

---

### 3. GET `/api/v1/portfolio/pnl`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadPortfolio()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Reads `total_realized_pnl`, `total_unrealized_pnl`. Drives `#p-stake` (Total Return), `#p-dpnl` (Today's Return base calculation). |
| **Router file** | `portfolio.py` → `PortfolioService.get_pnl_summary()` |

---

### 4. GET `/api/v1/positions/open`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadPortfolio()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Populates `openPos[]` array. Drives: `#p-open` (Active Predictions count), `#p-used` (Exposure), `#p-avail` (Available Capital), `#hb-pos` badge, per-market card position overlays (entry price, exposure, side glow, CONF, ENTRIES rows), `updatePipeCounts()`. |
| **Router file** | `positions.py` → `position_repository.get_open_positions()` |

---

### 5. GET `/api/v1/portfolio/summary`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadPortfolio()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Reads `sumD.executed_orders` (fallback label for win-rate subtitle when `win_rate` is null). Secondary usage only — primary portfolio data comes from endpoints 3, 4, 6, 7. |
| **Router file** | `portfolio.py` → `PortfolioService.get_portfolio_summary()` |

---

### 6. GET `/api/v1/analytics/performance`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadPortfolio()` — wrapped in `.catch(()=>null)` (optional) |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Reads `win_rate`, `total_trades`, `total_fees_usdc`. Drives `#p-wr` (Prediction Accuracy), `#p-wr-s` subtitle, `#p-fees` (Total Cost). Gracefully degrades to `—` if endpoint fails. |
| **Router file** | `analytics.py` → `PerformanceAnalyticsService.get_performance_analytics()` |

---

### 7. GET `/api/v1/analytics/capital`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadPortfolio()` — wrapped in `.catch(()=>null)` (optional) |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Reads `daily_pnl`, `drawdown_percent`. Drives `#p-dpnl` (Today's Return value), `#p-dpnl-s` percentage. Gracefully degrades if endpoint fails. |
| **Router file** | `analytics.py` → `CapitalManagementService.evaluate()` |

---

### 8. GET `/api/v1/health/detailed`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadHealth()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Reads `d.database`, `d.redis`, `d.engines{}`. Drives the System Health grid in `#hlth-panel` (Row 3 left) — one row per engine showing name + percentage. Also updates `#hlth-label` engine count. |
| **Router file** | `health.py` — checks DB/Redis + engine heartbeats via Redis |
| **Engines displayed** | universe_sync, price_refresh, signal_engine, opportunity_engine, strategy_engine, risk_engine, execution_engine, exit_engine, position_tracking, analytics_engine |

---

### 9. GET `/api/v1/price/active`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadClob()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Populates `clobPrices{}` keyed by `condition_id`. Drives per-card YES/NO probability display (`yes_mid`, `no_mid`), movement indicator (▲▼), and movement delta logic. This is the primary Polymarket probability data displayed on all 12 market cards. |
| **Router file** | `price.py` → `market_price_repository.get_latest_active_markets()` |

---

### 10. GET `/api/v1/universe/active`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadMarkets()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Populates `markets[]` array. Drives: Market Universe grid (Row 2) — all 12 market cards; `#hb-mkts` badge; `#univ-label` count; `opening_price` field used for TARGET (Price to Beat) display on each card; `end_time` for countdown timers; `status` for card state (MONITORING / UPCOMING / RESOLVED). |
| **Router file** | `universe.py` → `universe_repository.get_active_universe()` |

---

### 11. GET `/api/v1/opportunities?limit=50`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadMarkets()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Populates `opps{}` keyed by `condition_id`. Drives: CONF display on each market card (fallback when no signal), `avgConf` for asset column colour accent, `updatePipeCounts()` "scored" count. Also provides `open_positions` for capital/exposure calculations in `renderMarkets()`. |
| **Router file** | `opportunities.py` → `opportunity_repository.get_all_opportunities()` |

---

### 12. GET `/api/v1/signals/latest?limit=20`

| Property | Detail |
|---|---|
| **Classification** | **FE** |
| **Consumer function** | `loadMarkets()` |
| **Called from** | `refresh()` every 30 s |
| **Usage** | Populates `sigs{}` keyed by `condition_id`. Drives: CONF display on each market card (primary source — `confidence_score`), `#hb-sigs` badge count, `updatePipeCounts()` "active signals" count. |
| **Router file** | `signals.py` → `signal_repository.get_latest_signals()` |

---

## ENDPOINTS NOT FETCHED BY FRONTEND (UNU)

These endpoints exist in `backend/app/api/v1/` but have zero `fetch()` calls in `index.html`.

| Endpoint | Router File | Description |
|---|---|---|
| GET `/api/v1/health` | `health.py` | Basic health (DB + Redis only) |
| GET `/api/v1/price/latest` | `price.py` | All latest prices (superset of /active) |
| GET `/api/v1/price/stats` | `price.py` | Price statistics |
| GET `/api/v1/price/{condition_id}` | `price.py` | Single-market price detail |
| GET `/api/v1/signals/active` | `signals.py` | Active signals only |
| GET `/api/v1/signals/ranked` | `signals.py` | Signals sorted by significance |
| GET `/api/v1/signals/stats` | `signals.py` | Signal statistics |
| GET `/api/v1/signals/{condition_id}` | `signals.py` | Single-market signal |
| GET `/api/v1/opportunities/top` | `opportunities.py` | Top-scored opportunities |
| GET `/api/v1/opportunities/{condition_id}` | `opportunities.py` | Single-market opportunity |
| GET `/api/v1/universe` | `universe.py` | All markets (active + inactive) |
| POST `/api/v1/universe/sync` | `universe.py` | Manual sync trigger |
| GET `/api/v1/universe/{condition_id}` | `universe.py` | Single-market universe record |
| GET `/api/v1/decisions` | `decisions.py` | DecisionLog records |
| GET `/api/v1/decisions/stats` | `decisions.py` | Decision statistics |
| GET `/api/v1/decisions/{condition_id}` | `decisions.py` | Single-market decision log |
| GET `/api/v1/strategies` | `strategies.py` | All TradeDecision records |
| GET `/api/v1/strategies/active` | `strategies.py` | Active (PENDING/APPROVED) strategies |
| GET `/api/v1/strategies/stats` | `strategies.py` | Strategy statistics |
| GET `/api/v1/orders` | `orders.py` | All orders |
| GET `/api/v1/orders/open` | `orders.py` | Open/pending orders |
| GET `/api/v1/orders/stats` | `orders.py` | Order statistics |
| GET `/api/v1/orders/{order_id}` | `orders.py` | Single order detail |
| GET `/api/v1/positions` | `positions.py` | All positions (open + closed) |
| GET `/api/v1/positions/closed` | `positions.py` | Closed positions |
| GET `/api/v1/positions/stats` | `positions.py` | Position statistics |
| GET `/api/v1/positions/{position_id}` | `positions.py` | Single position detail |
| GET `/api/v1/risk` | `risk.py` | All risk events |
| GET `/api/v1/risk/blocked` | `risk.py` | BLOCKED decisions only |
| GET `/api/v1/risk/stats` | `risk.py` | Risk event statistics |
| GET `/api/v1/portfolio/positions` | `portfolio.py` | Portfolio position breakdown |
| GET `/api/v1/portfolio/orders` | `portfolio.py` | Portfolio order breakdown |
| GET `/api/v1/portfolio/risk` | `portfolio.py` | Portfolio risk summary |
| GET `/api/v1/outcome-learning` | `outcome_learning.py` | All outcome learning records |
| GET `/api/v1/outcome-learning/stats` | `outcome_learning.py` | Outcome learning statistics |
| GET `/api/v1/outcome-learning/{condition_id}` | `outcome_learning.py` | Single-market outcome |
| GET `/api/v1/engine-performance` | `engine_performance.py` | Per-engine accuracy stats |
| GET `/api/v1/engine-weights` | `engine_weights.py` | Per-engine current weights |
| GET `/api/v1/evaluation/summary` | `evaluation.py` | Trade evaluation summary |
| GET `/api/v1/evaluation/scorecard` | `evaluation.py` | Evaluation scorecard |
| GET `/api/v1/evaluation/grades` | `evaluation.py` | Evaluation grades |
| GET `/api/v1/evaluation/{position_id}` | `evaluation.py` | Single-position evaluation |
| POST `/api/v1/evaluation/run` | `evaluation.py` | Manual evaluation trigger |
| GET `/api/v1/replay/dataset` | `replay.py` | Replay dataset |
| GET `/api/v1/replay/{position_id}` | `replay.py` | Single-position replay |
| GET `/api/v1/trades` | `trades.py` | All trade records |
| GET `/api/v1/trades/{position_id}` | `trades.py` | Single trade detail |
| GET `/api/v1/momentum` | `momentum.py` | Momentum scores |
| GET `/api/v1/momentum/{asset}` | `momentum.py` | Per-asset momentum |
| GET `/api/v1/trend` | `trend.py` | Trend scores |
| GET `/api/v1/trend/{asset}` | `trend.py` | Per-asset trend |
| GET `/api/v1/volatility` | `volatility.py` | Volatility scores |
| GET `/api/v1/volatility/{asset}` | `volatility.py` | Per-asset volatility |
| GET `/api/v1/orderbook` | `orderbook.py` | Orderbook scores |
| GET `/api/v1/funding` | `funding.py` | Funding rate scores |
| GET `/api/v1/news` | `news.py` | News sentiment scores |
| GET `/api/v1/market-context` | `market_context.py` | Market context scores |
| GET `/api/v1/market-quality` | `market_quality.py` | Market quality scores |

---

## SUMMARY

| Classification | Count |
|---|---|
| **FE** (fetched by frontend) | **12** |
| **UNU** (exists, not fetched) | **~55** |
| **INT** (service-to-service, no HTTP) | all engine-to-engine calls |

**Only these 12 endpoints drive the visible dashboard.** The remaining ~55 are available for external API consumers, developer tooling, or future UI pages.

**Frontend data dependency:** The dashboard is entirely driven by probability and market data (endpoints 1, 2, 9, 10, 11, 12) plus paper-trading state (3, 4, 5, 6, 7) and system health (8). Removing the paper-trading layer would silence endpoints 3, 4, 5, 6, 7 — 5 of 12 FE endpoints.
