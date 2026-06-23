"""
Opportunity repository — Layer 5: Opportunity Engine.

All DB persistence and query operations for the `opportunities` table.
Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to maintain one current
row per active market (UPSERT by condition_id).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.opportunity import Opportunity
from app.models.market_universe import MarketUniverse

logger = get_logger(__name__)


async def upsert_opportunity(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    opportunity_score: float,
    score_mid_movement: float,
    score_spread: float,
    score_depth_imbalance: float,
    score_signal_activity: float,
    score_discovery: float,
    yes_mid: Optional[float],
    yes_bid: Optional[float],
    yes_ask: Optional[float],
    no_mid: Optional[float],
    spread_yes: Optional[float],
    spread_no: Optional[float],
    seed_deviation: Optional[float],
    signal_count_1h: int,
    last_signal_type: Optional[str],
    last_signal_severity: Optional[str],
    minutes_to_expiry: Optional[float],
    direction: str,
    evaluated_at: Optional[datetime] = None,
) -> None:
    """
    INSERT or UPDATE the opportunity row for a given condition_id.

    Uses PostgreSQL ON CONFLICT DO UPDATE so each active market has
    exactly one row reflecting its latest score.
    """
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)

    values = {
        "condition_id": condition_id,
        "asset": asset,
        "timeframe": timeframe,
        "opportunity_score": round(opportunity_score, 2),
        "score_mid_movement": round(score_mid_movement, 2),
        "score_spread": round(score_spread, 2),
        "score_depth_imbalance": round(score_depth_imbalance, 2),
        "score_signal_activity": round(score_signal_activity, 2),
        "score_discovery": round(score_discovery, 2),
        "yes_mid": yes_mid,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_mid": no_mid,
        "spread_yes": spread_yes,
        "spread_no": spread_no,
        "seed_deviation": seed_deviation,
        "signal_count_1h": signal_count_1h,
        "last_signal_type": last_signal_type,
        "last_signal_severity": last_signal_severity,
        "minutes_to_expiry": minutes_to_expiry,
        "direction": direction,
        "evaluated_at": evaluated_at,
    }

    update_values = {k: v for k, v in values.items() if k != "condition_id"}

    stmt = (
        pg_insert(Opportunity)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["condition_id"],
            set_=update_values,
        )
    )
    await session.execute(stmt)

    logger.debug(
        "Opportunity upserted",
        asset=asset,
        timeframe=timeframe,
        score=round(opportunity_score, 1),
        direction=direction,
    )


async def get_all_opportunities(
    session: AsyncSession,
    min_score: float = 0.0,
) -> list[Opportunity]:
    """Return all opportunity rows ordered by score descending."""
    stmt = (
        select(Opportunity)
        .where(Opportunity.opportunity_score >= min_score)
        .order_by(desc(Opportunity.opportunity_score))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_top_opportunities(
    session: AsyncSession,
    limit: int = 5,
    min_score: float = 10.0,
) -> list[Opportunity]:
    """Return the top N opportunities by score."""
    stmt = (
        select(Opportunity)
        .where(Opportunity.opportunity_score >= min_score)
        .order_by(desc(Opportunity.opportunity_score))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_opportunity_by_condition(
    session: AsyncSession,
    condition_id: str,
) -> Optional[Opportunity]:
    """Return the opportunity row for a specific condition_id."""
    result = await session.execute(
        select(Opportunity).where(Opportunity.condition_id == condition_id)
    )
    return result.scalar_one_or_none()


async def get_opportunity_count(session: AsyncSession) -> int:
    """Return total number of opportunity rows."""
    result = await session.execute(select(func.count()).select_from(Opportunity))
    return result.scalar_one()


async def get_active_opportunities(
    session: AsyncSession,
    min_score: float = 0.0,
) -> list[Opportunity]:
    """Return opportunities for currently-active universe markets only."""
    active_ids_stmt = (
        select(MarketUniverse.condition_id)
        .where(MarketUniverse.status == "active")
    )
    active_ids_result = await session.execute(active_ids_stmt)
    active_ids = [r[0] for r in active_ids_result.all()]

    if not active_ids:
        return []

    stmt = (
        select(Opportunity)
        .where(
            Opportunity.condition_id.in_(active_ids),
            Opportunity.opportunity_score >= min_score,
        )
        .order_by(desc(Opportunity.opportunity_score))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
