"""
Trend repository — Decision Engine pipeline, stage 3 (Trend).

UPSERT by (asset, timeframe), mirroring opportunity_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.trend_score import TrendScore

logger = get_logger(__name__)


async def upsert_trend_score(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    score: float,
    confidence: float,
    direction: str,
    reason: Optional[str],
    macd_line: Optional[float],
    macd_signal: Optional[float],
    macd_hist: Optional[float],
    ema_fast: Optional[float],
    ema_slow: Optional[float],
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
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k not in ("asset", "timeframe")}

    stmt = (
        pg_insert(TrendScore)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["asset", "timeframe"],
            set_=update_values,
        )
    )
    await session.execute(stmt)

    logger.debug(
        "Trend score upserted",
        asset=asset,
        timeframe=timeframe,
        score=round(score, 1),
        direction=direction,
    )


async def get_trend_score(
    session: AsyncSession, asset: str, timeframe: str
) -> Optional[TrendScore]:
    result = await session.execute(
        select(TrendScore).where(
            TrendScore.asset == asset, TrendScore.timeframe == timeframe
        )
    )
    return result.scalar_one_or_none()


async def get_all_trend_scores(session: AsyncSession) -> list[TrendScore]:
    result = await session.execute(select(TrendScore))
    return list(result.scalars().all())
