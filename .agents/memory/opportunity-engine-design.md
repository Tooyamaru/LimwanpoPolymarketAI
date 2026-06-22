---
name: Opportunity Engine design
description: Layer 5 Opportunity Engine — score formula, persistence, and the universe_ready deadlock fix
---

## Score Components (0–100 total)

| Component | Max | Formula |
|-----------|-----|---------|
| score_mid_movement | 30 | min(30, abs(yes_mid - 0.50) × 600) |
| score_spread | 20 | max(0, (0.02 - spread_yes) × 2000) |
| score_depth_imbalance | 20 | min(20, abs(spread_no - spread_yes) × 2000) |
| score_signal_activity | 20 | 0→10→15→20 by count (1h window); +3 per HIGH sev, cap 20 |
| score_discovery | 10 | time-to-expiry tiers: <15m=10, <30m=8, <60m=6, <2h=4, <6h=2, else=1, null=0 |

Direction: BUY_YES if mid < 0.495, BUY_NO if mid > 0.505, else NEUTRAL (±0.5% band)

## Persistence

UPSERT by condition_id using PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`.
One row per active market, always reflects latest assessment.
Run every 30s (OPPORTUNITY_ENGINE_INTERVAL_SECONDS).

**Why UPSERT not INSERT:** 12 markets × 30s = 1440 rows/hour would grow to noise.
Current score per market is what matters; history available via snapshots + signals.

## universe_ready Deadlock Fix

If `UNIVERSE_SYNC_RUN_ON_STARTUP=False` (Replit env var override), the universe_ready
asyncio.Event was never set, blocking all gated engines (price_refresh, signal, opportunity)
forever. Fix: in `_run_universe_sync_loop`, else-branch sets the event immediately:

```python
else:
    if universe_ready is not None:
        universe_ready.set()  # existing DB state is sufficient
```

**Why:** DB already has universe data from previous sessions. Run_on_startup=False
just means we skip the API refresh call at boot, not that the universe is empty.

## Files

- `backend/app/models/opportunity.py` — Opportunity ORM model
- `backend/app/services/opportunity_engine.py` — OpportunityEngine.evaluate()
- `backend/app/services/opportunity_repository.py` — upsert + queries
- `backend/app/api/v1/opportunities.py` — REST endpoints
- Integrated in `main.py` as `_run_opportunity_engine_loop()`
