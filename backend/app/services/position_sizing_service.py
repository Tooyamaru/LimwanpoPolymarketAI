"""
Position Sizing Service — Layer 13: Variable Position Sizing.

Converts an opportunity score into a USDC allocation size.

Sizing tiers (configured via settings):

  score >= POSITION_SCORE_MAX  (95) → POSITION_SIZE_MAX_USDC    (50 USDC)
  score >= POSITION_SCORE_HIGH (90) → POSITION_SIZE_MEDIUM_USDC (25 USDC)
  score >= POSITION_SCORE_MEDIUM(85)→ POSITION_SIZE_MIN_USDC    (10 USDC)
  score <  POSITION_SCORE_MEDIUM    → None  (skip — do not trade)

Returns None when the score is below the minimum threshold so the calling
engine can skip creating a TradeDecision entirely.
"""

from typing import Optional

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PositionSizingService:
    """
    Converts an opportunity score into a USDC position size.

    Usage::

        svc = PositionSizingService()
        size = svc.calculate(opportunity_score=87.5)
        # → 10.0  (POSITION_SIZE_MIN_USDC)

        size = svc.calculate(opportunity_score=72.0)
        # → None  (below minimum threshold — skip)
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
            USDC amount to allocate, or None when below minimum threshold.
        """
        if opportunity_score >= settings.POSITION_SCORE_MAX:
            size = settings.POSITION_SIZE_MAX_USDC
            tier = "MAX"
        elif opportunity_score >= settings.POSITION_SCORE_HIGH:
            size = settings.POSITION_SIZE_MEDIUM_USDC
            tier = "HIGH"
        elif opportunity_score >= settings.POSITION_SCORE_MEDIUM:
            size = settings.POSITION_SIZE_MIN_USDC
            tier = "MEDIUM"
        else:
            logger.debug(
                "Position sizing: score below minimum threshold — skipping",
                opportunity_score=round(opportunity_score, 2),
                min_threshold=settings.POSITION_SCORE_MEDIUM,
            )
            return None

        logger.debug(
            "Position sizing calculated",
            opportunity_score=round(opportunity_score, 2),
            tier=tier,
            position_size_usdc=size,
        )
        return float(size)
