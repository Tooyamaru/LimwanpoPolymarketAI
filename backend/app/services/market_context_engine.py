"""
Market Context Engine — Phase Next, supporting engine.

An asset must be read as ONE structure, not as isolated timeframes. This
engine groups the (supporting) Momentum Engine's directional reads across
every active timeframe for a given asset and reports whether the asset's
overall context is ALIGNED, MIXED, or in CONFLICT.

Read-only with respect to momentum_scores / market_universe — only reads
them and writes to its own market_context_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.momentum_score import MomentumScore
from app.repositories import market_context_repository as repo
from app.repositories.universe_repository import get_active_universe

logger = get_logger(__name__)


class MarketContextEngine:
    """
    Usage (from a background loop)::

        engine = MarketContextEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        universe = await get_active_universe(session)
        assets = sorted({m.asset for m in universe})

        scored = 0
        skipped = 0
        errors = 0

        for asset in assets:
            try:
                timeframes = sorted({m.timeframe for m in universe if m.asset == asset})
                result = await self._score_asset(session, asset, timeframes)
                if result is None:
                    skipped += 1
                    continue
                await repo.upsert_market_context_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error("Market context engine error", asset=asset, error=str(exc))
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Market context engine cycle complete",
            assets=len(assets),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"assets": len(assets), "scored": scored, "skipped": skipped, "errors": errors}

    @staticmethod
    async def _score_asset(session: AsyncSession, asset: str, timeframes: list[str]) -> dict | None:
        result = await session.execute(
            select(MomentumScore).where(
                MomentumScore.asset == asset, MomentumScore.timeframe.in_(timeframes)
            )
        )
        rows = list(result.scalars().all())
        if not rows:
            return None

        directions = {r.timeframe: r.direction for r in rows}
        values = list(directions.values())
        total = len(values)

        bullish = sum(1 for v in values if v == "BULLISH")
        bearish = sum(1 for v in values if v == "BEARISH")
        neutral = sum(1 for v in values if v == "NEUTRAL")

        detail = " ".join(f"{tf}={d}" for tf, d in sorted(directions.items()))

        if bullish == total or bearish == total:
            status = "ALIGNED"
            confidence = 100.0
            reason = f"All {total} timeframes agree — {detail}"
        elif bullish > 0 and bearish > 0:
            status = "CONFLICT"
            confidence = max(0.0, 100.0 * (1.0 - abs(bullish - bearish) / total))
            reason = f"Timeframes disagree in opposite directions — {detail}"
        else:
            status = "MIXED"
            dominant = max(bullish, bearish, neutral)
            confidence = round(dominant / total * 100.0, 2)
            reason = f"Partial agreement, no direct conflict — {detail}"

        return {
            "asset": asset,
            "status": status,
            "confidence": round(confidence, 2),
            "reason": reason,
            "timeframes_evaluated": ",".join(sorted(directions.keys())),
        }
