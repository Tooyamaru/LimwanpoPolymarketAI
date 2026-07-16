"""
Momentum repository — Decision Engine pipeline, stage 2 (Momentum).

UPSERT by (asset, timeframe), mirroring opportunity_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.momentum_score import MomentumScore

logger = get_logger(__name__)


async def upsert_momentum_score(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    score: float,
    confidence: float,
    direction: str,
    reason: Optional[str],
    roc_pct: Optional[float],
    rsi: Optional[float],
    ema_fast: Optional[float],
    ema_slow: Optional[float],
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
        "direction": direction,
        "reason": reason,
        "roc_pct": roc_pct,
        "rsi": rsi,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "last_close": last_close,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k not in ("asset", "timeframe")}

    stmt = (
        pg_insert(MomentumScore)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["asset", "timeframe"],
            set_=update_values,
        )
    )
    await session.execute(stmt)

    logger.debug(
        "Momentum score upserted",
        asset=asset,
        timeframe=timeframe,
        score=round(score, 1),
        direction=direction,
    )


async def get_momentum_score(
    session: AsyncSession, asset: str, timeframe: str
) -> Optional[MomentumScore]:
    result = await session.execute(
        select(MomentumScore).where(
            MomentumScore.asset == asset, MomentumScore.timeframe == timeframe
        )
    )
    return result.scalar_one_or_none()


async def get_all_momentum_scores(session: AsyncSession) -> list[MomentumScore]:
    result = await session.execute(select(MomentumScore))
    return list(result.scalars().all())
