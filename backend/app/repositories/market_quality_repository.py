"""
Market Quality repository — Polymarket Market Engine (Phase Next).

UPSERT by condition_id, mirroring momentum_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_quality_score import MarketQualityScore

logger = get_logger(__name__)


async def upsert_market_quality_score(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    market_score: float,
    market_quality: str,
    market_confidence: float,
    market_risk: str,
    reason: Optional[str],
    market_behaviours: Optional[str] = None,
    yes_bid: Optional[float] = None,
    yes_ask: Optional[float],
    spread_yes: Optional[float],
    liquidity: Optional[float],
    volume: Optional[float],
    seconds_to_expiry: Optional[float],
    active: Optional[bool],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "condition_id": condition_id,
        "asset": asset,
        "timeframe": timeframe,
        "market_score": round(market_score, 2),
        "market_quality": market_quality,
        "market_confidence": round(market_confidence, 2),
        "market_risk": market_risk,
        "reason": reason,
        "market_behaviours": market_behaviours,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "spread_yes": spread_yes,
        "liquidity": liquidity,
        "volume": volume,
        "seconds_to_expiry": seconds_to_expiry,
        "active": active,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k != "condition_id"}

    stmt = (
        pg_insert(MarketQualityScore)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["condition_id"],
            set_=update_values,
        )
    )
    await session.execute(stmt)

    logger.debug(
        "Market quality score upserted",
        condition_id=condition_id,
        asset=asset,
        quality=market_quality,
        score=round(market_score, 1),
    )


async def get_market_quality_score(
    session: AsyncSession, condition_id: str
) -> Optional[MarketQualityScore]:
    result = await session.execute(
        select(MarketQualityScore).where(MarketQualityScore.condition_id == condition_id)
    )
    return result.scalar_one_or_none()


async def get_all_market_quality_scores(session: AsyncSession) -> list[MarketQualityScore]:
    result = await session.execute(select(MarketQualityScore))
    return list(result.scalars().all())
