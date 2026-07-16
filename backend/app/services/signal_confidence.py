"""
Signal Confidence & Market Regime — AI Signal Engine Phase 1.

Provides two pure-function modules that enhance raw signals with
quality metadata before they are persisted.

Confidence Score (0–100)
------------------------
Combines signal type weight, severity tier, deviation magnitude,
and spread quality into a single tradeable confidence number.

  >= 70  : HIGH confidence — actionable entry candidate
  40–69  : MEDIUM confidence — worth watching
  < 40   : LOW confidence — informational only

Market Regime (RANGING | TRENDING_UP | TRENDING_DOWN | VOLATILE | UNKNOWN)
---------------------------------------------------------------------------
Classifies the current market micro-regime from the last N yes_mid
values.  Used downstream by the strategy engine to adjust thresholds
and by the signal ranker to weight signals appropriately.

  RANGING      — price oscillating tightly around seed (0.50)
  TRENDING_UP  — sustained upward drift across the observation window
  TRENDING_DOWN — sustained downward drift
  VOLATILE     — high variance with no clear trend
  UNKNOWN      — insufficient data

Multi-Timeframe Confirmation (bool)
------------------------------------
Set by the SignalEngine after a full cycle scan.  True when ≥ 2
timeframes for the same asset emitted signals in the same scan cycle
*or* have signals within the MTF_LOOKBACK_SECONDS window in the DB.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "compute_confidence",
    "detect_regime",
    "REGIME_RANGING",
    "REGIME_TRENDING_UP",
    "REGIME_TRENDING_DOWN",
    "REGIME_VOLATILE",
    "REGIME_UNKNOWN",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
]

REGIME_RANGING = "RANGING"
REGIME_TRENDING_UP = "TRENDING_UP"
REGIME_TRENDING_DOWN = "TRENDING_DOWN"
REGIME_VOLATILE = "VOLATILE"
REGIME_UNKNOWN = "UNKNOWN"

CONFIDENCE_HIGH = 70
CONFIDENCE_MEDIUM = 40

_TYPE_BASE: dict[str, float] = {
    "SEED_DEVIATION": 40.0,
    "MID_MOVE": 30.0,
    "SPREAD_CHANGE": 20.0,
}

_SEVERITY_MULT: dict[str, float] = {
    "HIGH": 1.00,
    "MEDIUM": 0.65,
    "LOW": 0.30,
}

_MAX_DEVIATION = 0.10
_MAX_DELTA = 0.05
_SPREAD_GOOD = 0.01
_SPREAD_BAD = 0.05


def compute_confidence(
    signal_type: str,
    severity: str,
    seed_deviation: Optional[float] = None,
    yes_mid_delta: Optional[float] = None,
    spread_after: Optional[float] = None,
) -> float:
    """
    Return a confidence score in [0, 100] for a single signal.

    Parameters
    ----------
    signal_type   : MID_MOVE | SEED_DEVIATION | SPREAD_CHANGE
    severity      : LOW | MEDIUM | HIGH
    seed_deviation: abs(yes_mid - 0.50), populated for SEED_DEVIATION signals
    yes_mid_delta : raw mid change, used if seed_deviation is absent
    spread_after  : current YES spread; tighter → higher quality

    Returns
    -------
    float rounded to 2 dp, clamped to [0, 100].
    """
    base = _TYPE_BASE.get(signal_type, 20.0)
    mult = _SEVERITY_MULT.get(severity, 0.30)

    # ── Magnitude bonus (0–30 pts) ────────────────────────────────────────────
    magnitude_bonus = 0.0
    if seed_deviation is not None and seed_deviation > 0:
        magnitude_bonus = min(seed_deviation / _MAX_DEVIATION, 1.0) * 30.0
    elif yes_mid_delta is not None and yes_mid_delta != 0:
        magnitude_bonus = min(abs(yes_mid_delta) / _MAX_DELTA, 1.0) * 20.0

    # ── Spread quality bonus (0–10 pts) ──────────────────────────────────────
    spread_bonus = 0.0
    if spread_after is not None:
        spread_ratio = (_SPREAD_BAD - spread_after) / (_SPREAD_BAD - _SPREAD_GOOD)
        spread_bonus = max(0.0, min(spread_ratio, 1.0)) * 10.0

    raw = base * mult + magnitude_bonus + spread_bonus
    return round(min(max(raw, 0.0), 100.0), 2)


def detect_regime(mids: list[float]) -> str:
    """
    Classify the current market micro-regime from a sequence of yes_mid prices.

    The list must be in chronological order (oldest first).  At least 3 values
    are required; fewer returns UNKNOWN.

    Algorithm
    ---------
    1. Compute average deviation from seed (0.50).
    2. If avg_dev < RANGING_THRESHOLD → RANGING (market still near seed).
    3. Compare the mean of the first half vs second half of the window.
       If the gap > TREND_THRESHOLD → TRENDING_UP or TRENDING_DOWN.
    4. Otherwise compute variance; above VOLATILE_THRESHOLD → VOLATILE.
    5. Default → RANGING.
    """
    n = len(mids)
    if n < 3:
        return REGIME_UNKNOWN

    avg = sum(mids) / n
    deviations = [abs(m - 0.50) for m in mids]
    avg_dev = sum(deviations) / n

    # ── Regime: RANGING — market hugging seed ────────────────────────────────
    RANGING_THRESHOLD = 0.005
    if avg_dev < RANGING_THRESHOLD:
        return REGIME_RANGING

    # ── Regime: TRENDING — directional drift ─────────────────────────────────
    half = n // 2
    first_avg = sum(mids[:half]) / half
    second_avg = sum(mids[half:]) / (n - half)
    trend_delta = second_avg - first_avg

    TREND_THRESHOLD = 0.010
    if trend_delta > TREND_THRESHOLD:
        return REGIME_TRENDING_UP
    if trend_delta < -TREND_THRESHOLD:
        return REGIME_TRENDING_DOWN

    # ── Regime: VOLATILE — high variance without trend ────────────────────────
    variance = sum((m - avg) ** 2 for m in mids) / n
    VOLATILE_THRESHOLD = 0.0001
    if variance > VOLATILE_THRESHOLD:
        return REGIME_VOLATILE

    return REGIME_RANGING
