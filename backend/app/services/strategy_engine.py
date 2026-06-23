"""
Strategy Engine — Layer 6.

Reads current Opportunity rows and applies rule-based decision logic to
produce TradeDecision records.

Decision rules (applied in order):

  1. spread_yes > SPREAD_THRESHOLD (0.02) → SKIP  (skip_reason=HIGH_SPREAD)
  2. direction == NEUTRAL               → SKIP  (skip_reason=NEUTRAL_DIRECTION)
  3. score >= SCORE_OPEN (40)
       direction == BUY_NO  → OPEN_LONG_NO
       direction == BUY_YES → OPEN_LONG_YES
  4. score >= SCORE_WATCH (20)          → WATCH
  5. score <  SCORE_WATCH (20)          → SKIP  (skip_reason=LOW_SCORE)

SKIP decisions are only persisted when STRATEGY_PERSIST_SKIPS is True.

The engine runs every STRATEGY_ENGINE_INTERVAL_SECONDS (default 60 s) and
is gated on the universe_ready event so it waits for the first universe
sync before its first cycle.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.services import opportunity_repository as opp_repo
from app.services import trade_decision_repository as td_repo

logger = get_logger(__name__)

SCORE_OPEN: float = 40.0
SCORE_WATCH: float = 20.0
SPREAD_THRESHOLD: float = 0.02


def _make_decision(
    score: float,
    direction: str,
    spread_yes: Optional[float],
) -> tuple[str, Optional[str]]:
    """
    Apply the strategy rules and return (decision, skip_reason).

    Returns
    -------
    decision   : OPEN_LONG_YES | OPEN_LONG_NO | WATCH | SKIP
    skip_reason: HIGH_SPREAD | NEUTRAL_DIRECTION | LOW_SCORE | None
    """
    if spread_yes is not None and spread_yes > SPREAD_THRESHOLD:
        return "SKIP", "HIGH_SPREAD"

    if direction == "NEUTRAL":
        return "SKIP", "NEUTRAL_DIRECTION"

    if score >= SCORE_OPEN:
        if direction == "BUY_NO":
            return "OPEN_LONG_NO", None
        if direction == "BUY_YES":
            return "OPEN_LONG_YES", None

    if score >= SCORE_WATCH:
        return "WATCH", None

    return "SKIP", "LOW_SCORE"


class StrategyEngine:
    """
    Applies strategy rules to all current Opportunity rows and persists
    TradeDecision records.

    Usage (from FastAPI lifespan or background loop)::

        engine = StrategyEngine()
        result = await engine.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        """
        Execute one full strategy cycle.

        Returns
        -------
        dict with cycle summary statistics.
        """
        started = datetime.now(timezone.utc)

        opportunities = await opp_repo.get_all_opportunities(session, min_score=0.0)

        if not opportunities:
            logger.debug("Strategy engine: no opportunities to evaluate")
            return {
                "opportunities_read": 0,
                "open_long_yes": 0,
                "open_long_no": 0,
                "watch": 0,
                "skip": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        counters: dict[str, int] = {
            "OPEN_LONG_YES": 0,
            "OPEN_LONG_NO": 0,
            "WATCH": 0,
            "SKIP": 0,
        }
        errors = 0
        persist_skips: bool = getattr(settings, "STRATEGY_PERSIST_SKIPS", False)

        for opp in opportunities:
            try:
                decision, skip_reason = _make_decision(
                    score=opp.opportunity_score,
                    direction=opp.direction,
                    spread_yes=opp.spread_yes,
                )
                counters[decision] = counters.get(decision, 0) + 1

                if decision == "SKIP" and not persist_skips:
                    continue

                await td_repo.insert_decision(
                    session,
                    condition_id=opp.condition_id,
                    asset=opp.asset,
                    timeframe=opp.timeframe,
                    decision=decision,
                    opportunity_score=opp.opportunity_score,
                    direction=opp.direction,
                    yes_mid=opp.yes_mid,
                    yes_bid=opp.yes_bid,
                    yes_ask=opp.yes_ask,
                    spread_yes=opp.spread_yes,
                    skip_reason=skip_reason,
                )
            except Exception as exc:
                logger.error(
                    "Strategy engine error",
                    condition_id=opp.condition_id[:12],
                    asset=opp.asset,
                    timeframe=opp.timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        logger.info(
            "Strategy engine cycle complete",
            opportunities_read=len(opportunities),
            open_long_yes=counters["OPEN_LONG_YES"],
            open_long_no=counters["OPEN_LONG_NO"],
            watch=counters["WATCH"],
            skip=counters["SKIP"],
            errors=errors,
            duration_ms=elapsed_ms,
        )

        return {
            "opportunities_read": len(opportunities),
            "open_long_yes": counters["OPEN_LONG_YES"],
            "open_long_no": counters["OPEN_LONG_NO"],
            "watch": counters["WATCH"],
            "skip": counters["SKIP"],
            "errors": errors,
            "duration_ms": elapsed_ms,
        }
