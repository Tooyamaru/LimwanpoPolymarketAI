"""
prediction_window.py — 5-minute slot and prediction-window helpers.

Pure functions; no external dependencies, no I/O.

Slot semantics
--------------
The timestamp slug represents the START of the five-minute window:

    slot = floor(unix_time / 300) * 300

At server time 05:42 UTC → slot = 05:40 UTC.
Prediction window: [slot, slot+300).

Event-slug format
-----------------
    {asset_lower}-updown-5m-{slot}

Examples:
    btc-updown-5m-1752937200
    eth-updown-5m-1752937500
"""

import math
from datetime import datetime, timezone
from typing import Optional

# Maps our canonical asset names to the slug prefix used in Gamma event slugs.
ASSET_SLUG_PREFIX: dict[str, str] = {
    "BTC": "btc",
    "ETH": "eth",
    "SOL": "sol",
    "XRP": "xrp",
}

SLOT_SECONDS = 300  # 5 minutes


def get_current_slot(now: Optional[datetime] = None) -> int:
    """
    Return the Unix timestamp of the START of the current 5-minute slot.

    Slot boundary semantics (inclusive start, exclusive end):
        slot = floor(unix_time / 300) * 300

    Examples:
        05:39:59 UTC → slot 05:35 UTC
        05:40:00 UTC → slot 05:40 UTC
        05:44:59 UTC → slot 05:40 UTC
        05:45:00 UTC → slot 05:45 UTC
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.timestamp()
    return int(math.floor(ts / SLOT_SECONDS) * SLOT_SECONDS)


def slot_to_datetime(slot: int) -> datetime:
    """Convert a Unix slot integer to a UTC-aware datetime."""
    return datetime.fromtimestamp(slot, tz=timezone.utc)


def build_event_slug(asset: str, slot: int) -> str:
    """
    Build the Gamma event slug for a given asset and slot.

    Format: {asset_lower}-updown-5m-{slot}

    Args:
        asset: canonical asset name ("BTC", "ETH", "SOL", "XRP")
        slot:  Unix timestamp of the slot start (multiple of 300)

    Returns:
        e.g. "btc-updown-5m-1752937200"
    """
    prefix = ASSET_SLUG_PREFIX.get(asset.upper(), asset.lower())
    return f"{prefix}-updown-5m-{slot}"


def get_candidate_slots(now: Optional[datetime] = None, lookahead: int = 3) -> list[int]:
    """
    Return an ordered list of slots to probe: [prev, current, next, next+1, ...].

    Args:
        now:       server time (defaults to UTC now)
        lookahead: how many future slots to include beyond current (default 3)

    Returns:
        List of slot Unix timestamps: previous slot + current slot + lookahead future slots.
    """
    current = get_current_slot(now)
    slots = [current - SLOT_SECONDS, current]
    for i in range(1, lookahead + 1):
        slots.append(current + i * SLOT_SECONDS)
    return slots


def slot_contains_time(slot: int, t: Optional[datetime] = None) -> bool:
    """
    Return True if time `t` falls within [slot, slot+300).
    """
    if t is None:
        t = datetime.now(timezone.utc)
    ts = t.timestamp()
    return slot <= ts < slot + SLOT_SECONDS
