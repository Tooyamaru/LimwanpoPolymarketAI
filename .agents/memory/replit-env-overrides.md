---
name: Replit env var overrides
description: Replit platform injects env vars that override settings.py defaults — critical for run_on_startup flags and version
---

## Known Replit-Injected Overrides

These environment variables are injected by Replit and OVERRIDE settings.py defaults:

```
APP_VERSION=0.4.0                    # overrides settings.py APP_VERSION
UNIVERSE_SYNC_RUN_ON_STARTUP=false   # overrides True default
PRICE_REFRESH_RUN_ON_STARTUP=false   # overrides True default
PRICE_REFRESH_ENABLED=true
PRICE_REFRESH_SECONDS=10
UNIVERSE_SYNC_ENABLED=true
UNIVERSE_SYNC_INTERVAL_SECONDS=60
```

## Impact

Because `UNIVERSE_SYNC_RUN_ON_STARTUP=false`, the `universe_ready` asyncio.Event
is never set in the startup path, blocking all gated downstream engines.

**Fix applied in `_run_universe_sync_loop`:**
Add else-branch that immediately sets universe_ready when run_on_startup=False.
This allows downstream engines (price_refresh, signal, opportunity) to proceed
using existing DB state from previous sessions.

## How to Check

```bash
printenv | grep -E "(UNIVERSE|PRICE_REFRESH|APP_VERSION|SIGNAL|OPPORTUNITY)"
```

## Why Not Change the Env Vars

These are Replit platform-managed secrets/env vars. They should not be changed
without user confirmation as they may be set intentionally (e.g., to reduce
API calls on cold start). The code fix is more robust — always handle the case
where run_on_startup=False regardless of why it was set.
