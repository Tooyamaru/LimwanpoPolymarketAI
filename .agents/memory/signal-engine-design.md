---
name: Signal Engine design
description: Layer 4 Signal Engine — architecture decisions, thresholds, deduplication, and integration pattern
---

## Signal Types & Thresholds

Calibrated from Audit #1–#5 empirical findings:

| Type | Threshold | Rationale |
|------|-----------|-----------|
| MID_MOVE | abs(yes_mid_delta) > 0.001 | Any real tick above noise floor |
| SEED_DEVIATION | abs(yes_mid - 0.50) >= 0.01 | 1% deviation = meaningful market move |
| SPREAD_CHANGE | abs(spread_delta) >= 0.005 | 0.5% spread shift = LP activity |

Severity:
- MID_MOVE/SEED_DEV: LOW<0.01, MEDIUM 0.01-0.05, HIGH>=0.05
- SPREAD_CHANGE: LOW<0.01, MEDIUM 0.01-0.02, HIGH>=0.02

## Deduplication

For each (condition_id, signal_type), compares new value against `get_last_signal_for_market()`.
Skips if `yes_mid_after` (or `spread_after`) matches the last stored signal.
Prevents re-emitting the same state every 10s poll cycle.

**Why:** At AMM init phase 100% of markets are static; without dedup the `signals` table fills with thousands of identical rows on every cycle.

## Integration Pattern

Signal loop uses the same `universe_ready` asyncio.Event gate as price_refresh.
Runs every `SIGNAL_ENGINE_INTERVAL_SECONDS` (default 10s, same as price refresh).
Queries 2 latest snapshots per active market from `market_price_snapshots`.

## Current Empirical State (as of 2026-06-22)

Markets at 0.50 (1H) and 0.505 (5m/15m). Max deviation = 0.005 < threshold 0.01.
Zero signals expected until a real trade pushes a market ≥1% from seed.
This is the correct behavior — confirmed by Audit #5 findings.

## Files

- `backend/app/models/signal.py` — Signal ORM model
- `backend/app/services/signal_engine.py` — SignalEngine.scan()
- `backend/app/services/signal_repository.py` — DB operations
- `backend/app/api/v1/signals.py` — REST endpoints
- Integrated in `main.py` as `_run_signal_engine_loop()`
