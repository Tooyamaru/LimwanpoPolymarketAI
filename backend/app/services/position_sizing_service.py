"""
Position Sizing Service — Layer 13: Continuous Variable Sizing (Phase 12L).

Converts an opportunity score into a USDC allocation using a smooth
exponential curve, replacing the old fixed quality-range tiers.

Sizing logic:
  score < POSITION_SCORE_MEDIUM  → None  (skip — do not trade)
  score ≥ POSITION_SCORE_MEDIUM  → exponential interpolation from
                                   POSITION_SIZE_MIN_USDC to POSITION_SIZE_MAX_USDC

Formula:
  fraction = clamp((score - POSITION_SCORE_MEDIUM) /
                   (POSITION_SCORE_MAX  - POSITION_SCORE_MEDIUM), 0.0, 1.0)
  size     = POSITION_SIZE_MIN_USDC × (POSITION_SIZE_MAX_USDC /
                                       POSITION_SIZE_MIN_USDC) ^ fraction

LOT labels (LOT 1, LOT 2, LOT 3 …) are assigned by entry_sequence in the
position model and are entirely independent of the dollar allocation.

Returns None when the score is below the minimum threshold so the calling
engine can skip creating a TradeDecision entirely.
"""

import math
from typing import Optional

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PositionSizingService:
    """
    Converts an opportunity score into a continuous USDC position size.

    The allocation grows exponentially from POSITION_SIZE_MIN_USDC at the
    entry threshold (POSITION_SCORE_MEDIUM) to POSITION_SIZE_MAX_USDC at
    POSITION_SCORE_MAX and above — producing sub-dollar granularity at low
    scores and larger allocations at high-conviction signals.

    Usage::

        svc = PositionSizingService()

        svc.calculate(opportunity_score=20.0)   # → None  (below threshold)
        svc.calculate(opportunity_score=30.0)   # → 1.00  (MIN, at threshold)
        svc.calculate(opportunity_score=35.0)   # → 2.66  (continuous)
        svc.calculate(opportunity_score=40.0)   # → 7.07  (continuous)
        svc.calculate(opportunity_score=50.0)   # → 50.0  (MAX, capped)
        svc.calculate(opportunity_score=80.0)   # → 50.0  (above MAX — capped)
    """

    def calculate(self, opportunity_score: float) -> Optional[float]:
        """
        Return the USDC allocation for the given score, or None to skip.

        Parameters
        ----------
        opportunity_score : float
            Raw score from the Opportunity Engine (0–100).

        Returns
        -------
        float | None
            USDC amount to allocate (≥ POSITION_SIZE_MIN_USDC), or None when
            the score is below POSITION_SCORE_MEDIUM.
        """
        score_min = settings.POSITION_SCORE_MEDIUM
        score_max = settings.POSITION_SCORE_MAX
        size_min = settings.POSITION_SIZE_MIN_USDC
        size_max = settings.POSITION_SIZE_MAX_USDC

        if opportunity_score < score_min:
            logger.debug(
                "Position sizing: score below minimum threshold — skipping",
                opportunity_score=round(opportunity_score, 2),
                min_threshold=score_min,
            )
            return None

        # Clamp fraction to [0, 1] — scores above POSITION_SCORE_MAX get MAX size
        score_range = max(score_max - score_min, 1e-9)  # guard divide-by-zero
        fraction = min(1.0, max(0.0, (opportunity_score - score_min) / score_range))

        # Exponential curve: size = min × (max/min)^fraction
        if size_min <= 0:
            size_min = 0.01  # safety floor
        size = size_min * math.pow(size_max / size_min, fraction)
        size = round(min(size, size_max), 2)

        logger.debug(
            "Position sizing calculated (continuous)",
            opportunity_score=round(opportunity_score, 2),
            fraction=round(fraction, 4),
            position_size_usdc=size,
        )
        return size

    def get_tier_label(self, opportunity_score: float) -> str:
        """
        Return a descriptive label for the given score's sizing band.

        Labels are approximate quality buckets for logging/display only —
        the actual size is a continuous value, not a discrete tier.
        """
        score_min = settings.POSITION_SCORE_MEDIUM
        score_max = settings.POSITION_SCORE_MAX
        if opportunity_score < score_min:
            return "SKIP"
        score_range = max(score_max - score_min, 1e-9)
        fraction = min(1.0, max(0.0, (opportunity_score - score_min) / score_range))
        if fraction >= 1.0:
            return "MAX"
        elif fraction >= 0.5:
            return "HIGH"
        elif fraction >= 0.2:
            return "MEDIUM"
        return "LOW"
