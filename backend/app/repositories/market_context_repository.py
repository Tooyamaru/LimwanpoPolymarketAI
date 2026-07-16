"""
Market Context repository — Market Context Engine (Phase Next).

UPSERT by asset, mirroring momentum_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_context_score import MarketContextScore

logger = get_logger(__name__)


async def upsert_market_context_score(
    session: AsyncSession,
    *,
    asset: str,
    status: str,
    confidence: float,
    reason: Optional[str],
    timeframes_evaluated: Optional[str],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "asset": asset,
        "status": status,
        "confidence": round(confidence, 2),
        "reason": reason,
        "timeframes_evaluated": timeframes_evaluated,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k != "asset"}

    stmt = (
        pg_insert(MarketContextScore)
        .values(**values)
        .on_conflict_do_update(index_elements=["asset"], set_=update_values)
    )
    await session.execute(stmt)

    logger.debug("Market context score upserted", asset=asset, status=status)


async def get_market_context_score(
    session: AsyncSession, asset: str
) -> Optional[MarketContextScore]:
    result = await session.execute(
        select(MarketContextScore).where(MarketContextScore.asset == asset)
    )
    return result.scalar_one_or_none()


async def get_all_market_context_scores(session: AsyncSession) -> list[MarketContextScore]:
    result = await session.execute(select(MarketContextScore))
    return list(result.scalars().all())
