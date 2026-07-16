"""
Volatility repository — Decision Engine pipeline, stage 4 (Volatility).

UPSERT by (asset, timeframe), mirroring opportunity_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.volatility_score import VolatilityScore

logger = get_logger(__name__)


async def upsert_volatility_score(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    score: float,
    confidence: float,
    regime: str,
    reason: Optional[str],
    atr: Optional[float],
    atr_pct: Optional[float],
    last_close: Optional[float],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "asset": asset,
        "timeframe": timeframe,
        "score": round(score, 2),
        "confidence": round(confidence, 2),
        "regime": regime,
        "reason": reason,
        "atr": atr,
        "atr_pct": atr_pct,
        "last_close": last_close,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k not in ("asset", "timeframe")}

    stmt = (
        pg_insert(VolatilityScore)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["asset", "timeframe"],
            set_=update_values,
        )
    )
    await session.execute(stmt)

    logger.debug(
        "Volatility score upserted",
        asset=asset,
        timeframe=timeframe,
        score=round(score, 1),
        regime=regime,
    )


async def get_volatility_score(
    session: AsyncSession, asset: str, timeframe: str
) -> Optional[VolatilityScore]:
    result = await session.execute(
        select(VolatilityScore).where(
            VolatilityScore.asset == asset, VolatilityScore.timeframe == timeframe
        )
    )
    return result.scalar_one_or_none()


async def get_all_volatility_scores(session: AsyncSession) -> list[VolatilityScore]:
    result = await session.execute(select(VolatilityScore))
    return list(result.scalars().all())
