---
name: Market card data pipeline
description: Market card renderCard() JS function — row layout and variable ordering rules
---

**Row layout (final, verified working):**
- Row 1: YES mid | NO mid | status badge | countdown
- Row 2 (`.mc-ptb`, 3 col): Price to Beat | Current Price | Difference
- Row 3 (`.mc-r3`, 5 col inline): YES BID | YES ASK | NO BID | NO ASK | SPREAD
- Row 4 (`.mc-r4`): Position | Stake | Contracts | PnL | AI Score | Age

**Data sources:**
- Current Price = `cPrices[m.asset]` (from `/api/v1/crypto/ticker`, fetched every 15s). Can be object `{price, pct, ...}` or plain number — check with `typeof _at === "object"`.
- Price to Beat = `m.opening_price` (from MarketUniverse, set by MarketReferenceService from Binance candle at market start_time)
- Contracts = `pos.quantity` (from position model)
- AI Score = `opps[m.condition_id].opportunity_score` (already loaded in `loadMarkets()`)

**Temporal dead zone rule (critical):**
JS `const` declarations in `renderCard()` must appear in dependency order. `contractsStr` uses `hasPosn` and `pos` — it MUST be declared AFTER `const hasPosn=!!pos;`. Inserting new variables that reference `hasPosn` before the position block will throw `ReferenceError: Cannot access 'hasPosn' before initialization`.

**Why this matters:** The renderCard function is several hundred lines; block order is not obvious. Always grep for `hasPosn` declaration line before adding `hasPosn`-dependent variables.
