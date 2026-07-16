---
name: Watchdog and Engine Health
description: How engine liveness tracking, heartbeat registry, and auto-restart watchdog work.
---

# Engine Health & Watchdog

## Architecture
- `backend/app/core/engine_health.py` — module-level heartbeat registry
  - `_heartbeats: Dict[str, datetime]` — last successful cycle per engine
  - `_registered: List[str]` — all enabled engine names (set at startup)
  - `record_heartbeat(name)` — called after every successful engine cycle
  - `register_engines(names)` — called unconditionally from main.py lifespan()
  - `seconds_since(name, now=None)` — age in seconds, None if never cycled
  - `get_heartbeats()` / `get_registered()` — shallow-copy accessors

- `backend/app/workers/watchdog.py` — async background loop
  - Grace period: WATCHDOG_GRACE_SECONDS (120s) before first check
  - After grace: monitors every WATCHDOG_CHECK_SECONDS (60s)
  - If age > WATCHDOG_STALL_SECONDS (300s): WARNING log
  - If age > WATCHDOG_RESTART_SECONDS (600s): CRITICAL + sys.exit(1)
  - Engines with age=None escalate after WATCHDOG_RESTART_SECONDS of monitoring

- `backend/app/workers/engine_workers.py` — all 9 loops call record_heartbeat() after every successful _one_cycle()

- `/api/v1/health/detailed` — shows per-engine status (alive/stalled/not_started)
  - Iterates registered list, not just heartbeats dict
  - not_started degrades overall health only if uptime > WATCHDOG_STALL_SECONDS

## Key design decisions
**Why vm deployment target?** Bot has 9 asyncio background engines. Autoscale would shut down between requests, killing all engines. Multiple gunicorn workers would spawn duplicate engine instances → duplicate trades.

**Why single-process uvicorn?** Gunicorn multi-worker mode creates one asyncio event loop per worker, which would run all 9 engines N times simultaneously. Production command omits --reload.

**Why register_engines always (not just when WATCHDOG_ENABLED)?** Health endpoint must show all engines even when watchdog is off. Decoupled from watchdog toggle.

**Why not degrade on not_started immediately?** During normal boot (within grace window), engines wait behind universe_ready gate. After WATCHDOG_STALL_SECONDS uptime, not_started becomes a genuine degradation.

## Engine names registered
universe_sync, price_refresh, signal_engine, opportunity_engine, exit_engine, strategy_engine, risk_engine, execution_engine, position_tracking
