---
name: DEF-002 startup race fix
description: Race condition between universe_sync and price_refresh at startup; asyncio.Event fix in main.py
---

**Problem:** `main.py` `lifespan()` calls `asyncio.create_task()` for universe_sync then price_refresh in immediate succession with no coordination. Both tasks start simultaneously. Price refresh queries `market_universe WHERE status='active'` before universe_sync has updated the table, getting stale condition IDs from the prior session. Those IDs return `bid=0.01, spread=0.98` (empty orderbook) — contaminating the first ~2 minutes of snapshots on every restart.

**Fix (Sprint 9.5):** Added `universe_ready_event = asyncio.Event()` in `lifespan()`. Passed to both loop functions:
- `_run_universe_sync_loop` sets the event in a `finally` block after its first sync attempt (succeeds or fails)
- `_run_price_refresh_loop` awaits the event before its startup `_one_cycle()` call

**Verification:** After applying the fix, first 24 post-restart snapshots all show `min_bid=0.49, max_spread=0.02` — zero contamination.

**Why:** The event is set in `finally` so price refresh is never permanently blocked even if universe sync fails at startup.

**How to apply:** If re-opening `main.py` task loop structure, check that `universe_ready_event` is still wired to both `_run_universe_sync_loop` and `_run_price_refresh_loop` calls.
