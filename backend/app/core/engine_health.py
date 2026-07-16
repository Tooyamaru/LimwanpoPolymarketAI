"""
core/engine_health.py — Module-level engine heartbeat registry.

Each background engine calls record_heartbeat(name) after every successful
cycle.  The watchdog and /health/detailed endpoint read this registry to
determine which engines are alive, stalled, or have never run.

Thread / concurrency safety
---------------------------
All engines run inside the same asyncio event loop (single-threaded), so
plain dict operations are inherently safe — no locks needed.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

# Maps engine_name → timestamp of most recent successful cycle.
_heartbeats: Dict[str, datetime] = {}

# Ordered list of engine names that are enabled and expected to cycle.
# Populated by register_engines() at startup so /health/detailed can
# report *all* enabled engines, including those not yet run.
_registered: List[str] = []


def register_engines(names: List[str]) -> None:
    """
    Register the complete list of enabled engine names.

    Called once from main.py lifespan() after all engines have been
    started.  Provides the ground truth for which engines should be
    cycling, used by /health/detailed and the watchdog.
    """
    global _registered
    _registered = list(names)


def get_registered() -> List[str]:
    """Return the ordered list of registered engine names."""
    return list(_registered)


def record_heartbeat(engine: str) -> None:
    """Record the current UTC timestamp as the latest cycle for *engine*."""
    _heartbeats[engine] = datetime.now(timezone.utc)


def seconds_since(engine: str, now: Optional[datetime] = None) -> Optional[float]:
    """
    Return the number of seconds since *engine* last cycled.

    Returns ``None`` if *engine* has never been registered (never cycled).
    Pass *now* explicitly in tests to avoid real-time dependency.
    """
    last = _heartbeats.get(engine)
    if last is None:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    return (now - last).total_seconds()


def get_heartbeats() -> Dict[str, datetime]:
    """Return a shallow copy of the full heartbeat registry."""
    return dict(_heartbeats)
