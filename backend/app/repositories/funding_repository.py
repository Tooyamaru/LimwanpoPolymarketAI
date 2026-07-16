"""
Funding repository — Funding Engine (Phase Next, supporting engine).

UPSERT by asset, mirroring momentum_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.funding_score import FundingScore

logger = get_logger(__name__)


async def upsert_funding_score(
    session: AsyncSession,
    *,
    asset: str,
    direction: str,
    confidence: float,
    reason: Optional[str],
    funding_rate: Optional[float],
    open_interest: Optional[float],
    long_short_ratio: Optional[float],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "asset": asset,
        "direction": direction,
        "confidence": round(confidence, 2),
        "reason": reason,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "long_short_ratio": long_short_ratio,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k != "asset"}

    stmt = (
        pg_insert(FundingScore)
        .values(**values)
        .on_conflict_do_update(index_elements=["asset"], set_=update_values)
    )
    await session.execute(stmt)

    logger.debug("Funding score upserted", asset=asset, direction=direction)


async def get_funding_score(session: AsyncSession, asset: str) -> Optional[FundingScore]:
    result = await session.execute(
        select(FundingScore).where(FundingScore.asset == asset)
    )
    return result.scalar_one_or_none()


async def get_all_funding_scores(session: AsyncSession) -> list[FundingScore]:
    result = await session.execute(select(FundingScore))
    return list(result.scalars().all())
