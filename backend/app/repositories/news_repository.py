"""
News repository — News Engine (Phase Next, supporting engine — DEFERRED).

UPSERT by asset, mirroring momentum_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news_score import NewsScore

logger = get_logger(__name__)


async def upsert_news_score(
    session: AsyncSession,
    *,
    asset: str,
    sentiment: str,
    confidence: float,
    reason: Optional[str],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "asset": asset,
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "reason": reason,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k != "asset"}

    stmt = (
        pg_insert(NewsScore)
        .values(**values)
        .on_conflict_do_update(index_elements=["asset"], set_=update_values)
    )
    await session.execute(stmt)

    logger.debug("News score upserted", asset=asset, sentiment=sentiment)


async def get_news_score(session: AsyncSession, asset: str) -> Optional[NewsScore]:
    result = await session.execute(select(NewsScore).where(NewsScore.asset == asset))
    return result.scalar_one_or_none()


async def get_all_news_scores(session: AsyncSession) -> list[NewsScore]:
    result = await session.execute(select(NewsScore))
    return list(result.scalars().all())
