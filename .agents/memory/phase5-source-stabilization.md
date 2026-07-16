---
name: Phase 5 Source Stabilization pattern
description: How hardcoded/random dashboard values were traced to real sources; pattern for future "every value must trace to one source" audits.
---

Every dashboard value in LIMWANPO AI must trace to exactly one of: Polymarket (probability),
Binance/Chainlink (BTC chart only), or an internal engine calculation. `SOURCE_AUDIT.md`
is the living audit document — read it first before re-auditing, it already lists
FAIL/RISK items with root causes.

**Real activity feed pattern:** instead of faking "AI activity" messages, build a
`GET /api/v1/feed/recent` endpoint that merges existing engine-written rows
(Signal.detected_at, RiskEvent.checked_at, DecisionLog.created_at) chronologically.
No new tables needed — every engine already logs what it did to its own table.

**Frontend polling dedup gotcha:** when polling a feed endpoint on an interval and
appending only new items to a capped list (e.g. last 80), rebuild the dedup Set from
the *current* capped list on every poll — don't accumulate keys in a separate
ever-growing Set, or it leaks memory for the life of the tab.

**Confidence-uniformity investigations:** if a computed score looks suspiciously
identical across many rows, check whether it's legitimately deterministic
(same formula + same/near-identical inputs) before assuming it's hardcoded — verify
by reading the compute function itself, not just the output distribution. See
market-maturity.md for why Polymarket AMM markets in the early init phase produce
near-identical signal inputs.
