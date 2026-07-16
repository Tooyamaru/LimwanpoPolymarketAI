---
name: Market lifetimes and rotation
description: Prediction market window durations, rotation frequency, and what 5m/15m/1H names mean
---

The "5m", "15m", "1H" naming refers to the **underlying price movement window being predicted** (e.g., "will BTC be higher 5 minutes from the reference time?"), NOT the market's expiry duration.

**Actual market lifetimes (measured 2026-06-19):**
- `5m` markets: ~24 hours each
- `15m` markets: ~24 hours each
- `1H` markets: ~48-49 hours each

**Rotation:**
- Each (asset, timeframe) pair has exactly 1 `active` market at any time
- Pool of `upcoming` markets: ~22-27 per (asset, timeframe) combination
- Expected rotation: ~1 per day for 5m/15m, ~every 2 days for 1H
- Universe sync manages promotion/demotion via `demote_excess_active_markets`

**Signal implication:** Any signal model must partition by `market_universe_id`, not just `(asset, timeframe)`, and track ticks-since-activation. On rotation day, the rolling window resets to 0 observations for the new market.

**Condition ID churn:** In the first 32 min after restart (with DEF-002), saw 7 distinct condition IDs for 5m markets due to rapid universe sync cycling. Post-stabilization, rotation is ~1/day.
