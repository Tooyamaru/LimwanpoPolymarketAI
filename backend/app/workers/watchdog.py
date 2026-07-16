"""
workers/watchdog.py — Heartbeat watchdog for all background engines.

Monitors engine_health heartbeats on a configurable interval.  Raises
a WARNING when an engine hasn't cycled for WATCHDOG_STALL_SECONDS and
forces sys.exit(1) when an engine exceeds WATCHDOG_RESTART_SECONDS.
The Replit workflow manager detects the process exit and automatically
restarts the application, satisfying the "restarts if it crashes" requirement.

Severity escalation
-------------------
  age > WATCHDOG_STALL_SECONDS   → WARNING  (alert only, keep running)
  age > WATCHDOG_RESTART_SECONDS → CRITICAL + sys.exit(1)  (triggers restart)

Note: an engine whose heartbeat is None (never ran) is logged as a warning
but does not trigger a restart — it may still be waiting behind the
universe_ready gate on first boot.
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.config.settings import settings
from app.core import engine_health
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_watchdog_loop(enabled_engines: list[str]) -> None:
    """
    Background watchdog coroutine.

    Waits WATCHDOG_GRACE_SECONDS before beginning checks so all engines
    have time to complete their startup cycle after the universe_ready gate.

    Parameters
    ----------
    enabled_engines:
        Names of engines that are expected to be cycling.  Built by main.py
        based on which engines are actually enabled via settings flags.
    """
    grace = settings.WATCHDOG_GRACE_SECONDS
    check_interval = settings.WATCHDOG_CHECK_SECONDS
    stall_secs = settings.WATCHDOG_STALL_SECONDS
    restart_secs = settings.WATCHDOG_RESTART_SECONDS

    logger.info(
        "Watchdog: grace period started",
        grace_seconds=grace,
        monitored_engines=enabled_engines,
    )
    await asyncio.sleep(grace)
    logger.info("Watchdog: grace period ended — monitoring engine heartbeats")

    # Track when active monitoring began so we can escalate engines that have
    # *never* cycled after the grace period.
    monitoring_start = datetime.now(timezone.utc)

    while True:
        now = datetime.now(timezone.utc)
        monitoring_age = (now - monitoring_start).total_seconds()

        for name in enabled_engines:
            age = engine_health.seconds_since(name, now=now)

            if age is None:
                # Engine has never completed a cycle since startup.
                # After restart_secs of monitoring this is a hard stall.
                if monitoring_age > restart_secs:
                    logger.critical(
                        "Watchdog: engine has never cycled — forcing restart",
                        engine=name,
                        monitoring_seconds=round(monitoring_age, 1),
                        restart_threshold=restart_secs,
                    )
                    sys.exit(1)
                elif monitoring_age > stall_secs:
                    logger.warning(
                        "Watchdog: engine has not cycled since startup",
                        engine=name,
                        monitoring_seconds=round(monitoring_age, 1),
                        warn_threshold=stall_secs,
                    )
                continue

            if age > restart_secs:
                logger.critical(
                    "Watchdog: engine stall exceeds restart threshold — forcing restart",
                    engine=name,
                    stall_seconds=round(age, 1),
                    restart_threshold=restart_secs,
                )
                sys.exit(1)

            if age > stall_secs:
                logger.warning(
                    "Watchdog: engine appears stalled",
                    engine=name,
                    stall_seconds=round(age, 1),
                    warn_threshold=stall_secs,
                )

        await asyncio.sleep(check_interval)
