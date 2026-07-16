---
name: Dynamic weight watchdog fix
description: Why dynamic_weight caused watchdog restarts and how it was fixed.
---

## The problem

`dynamic_weight` is enabled but `DYNAMIC_WEIGHT_RUN_ON_STARTUP=False` and
`DYNAMIC_WEIGHT_INTERVAL_SECONDS=1800` (30 min).  The watchdog restarts the
process after `WATCHDOG_RESTART_SECONDS=600` (10 min) of a stale engine.

With a naive `while True: sleep(1800); work(); heartbeat()` loop the engine
never sends a heartbeat until 30 minutes in — far past the 10-minute kill
threshold.

## The fix (engine_workers.py — run_dynamic_weight_loop)

Two-part solution:

1. **Initial heartbeat** — emit `engine_health.record_heartbeat("dynamic_weight")`
   immediately after the optional startup run block, before `while True`.
   Prevents `age=None` which the watchdog treats as a crash after grace.

2. **Chunked sleep** — replace `await asyncio.sleep(1800)` with a loop that
   sleeps in `WATCHDOG_RESTART_SECONDS // 2` (≤300 s) chunks, emitting a
   liveness heartbeat between each chunk.  Keeps heartbeat age well under
   the 600 s restart threshold for the entire 30-min waiting period.

**Why:** A single startup heartbeat is not sufficient — it goes stale after
600 s while the loop waits 1800 s.  Chunked sleep ensures liveness signals
arrive every ≤5 min regardless of how long the work interval is.

## Pattern to watch

Any worker where `RUN_ON_STARTUP=False` AND `INTERVAL > WATCHDOG_RESTART_SECONDS`
needs the same chunked-sleep treatment.  Currently only `dynamic_weight` has
this profile; all other workers have intervals ≤300 s.
