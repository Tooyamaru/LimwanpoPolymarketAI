"""
Market price repository — Sprint 9.

All DB persistence and query operations for market_price_snapshots.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_universe import MarketUniverse

logger = get_logger(__name__)


async def save_snapshot(
    session: AsyncSession,
    *,
    market_universe_id: Optional[int],
    condition_id: str,
    yes_token_id: Optional[str],
    no_token_id: Optional[str],
    yes_bid: Optional[float],
    yes_ask: Optional[float],
    yes_mid: Optional[float],
    no_bid: Optional[float],
    no_ask: Optional[float],
    no_mid: Optional[float],
    spread_yes: Optional[float],
    spread_no: Optional[float],
    volume: Optional[float],
    liquidity: Optional[float],
    captured_at: Optional[datetime] = None,
) -> MarketPriceSnapshot:
    """Insert a new price snapshot row and return it."""
    if captured_at is None:
        captured_at = datetime.now(timezone.utc)

    snapshot = MarketPriceSnapshot(
        market_universe_id=market_universe_id,
        condition_id=condition_id,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        yes_mid=yes_mid,
        no_bid=no_bid,
        no_ask=no_ask,
        no_mid=no_mid,
        spread_yes=spread_yes,
        spread_no=spread_no,
        volume=volume,
        liquidity=liquidity,
        captured_at=captured_at,
    )
    session.add(snapshot)
    await session.flush()
    logger.debug(
        "Price snapshot saved",
        condition_id=condition_id[:12],
        yes_mid=yes_mid,
        no_mid=no_mid,
    )
    return snapshot


async def get_latest_snapshot(
    session: AsyncSession,
    limit: int = 50,
) -> list[MarketPriceSnapshot]:
    """Return the most recent `limit` snapshots across all markets."""
    result = await session.execute(
        select(MarketPriceSnapshot)
        .order_by(desc(MarketPriceSnapshot.captured_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_by_condition(
    session: AsyncSession,
    condition_id: str,
    limit: int = 1,
) -> list[MarketPriceSnapshot]:
    """
    Return the latest `limit` snapshots for a specific condition_id,
    ordered newest first.
    """
    result = await session.execute(
        select(MarketPriceSnapshot)
        .where(MarketPriceSnapshot.condition_id == condition_id)
        .order_by(desc(MarketPriceSnapshot.captured_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_active_markets(
    session: AsyncSession,
) -> list[MarketPriceSnapshot]:
    """
    Return one (the most recent) snapshot per active market_universe row.

    Joins market_price_snapshots → market_universe to resolve asset/timeframe,
    then picks the latest snapshot per condition_id.
    """
    active_ids_stmt = (
        select(MarketUniverse.condition_id)
        .where(MarketUniverse.status == "active")
    )
    active_ids_result = await session.execute(active_ids_stmt)
    active_condition_ids = [r[0] for r in active_ids_result.all()]

    if not active_condition_ids:
        return []

    subq = (
        select(
            MarketPriceSnapshot.condition_id,
            func.max(MarketPriceSnapshot.captured_at).label("max_ts"),
        )
        .where(MarketPriceSnapshot.condition_id.in_(active_condition_ids))
        .group_by(MarketPriceSnapshot.condition_id)
        .subquery()
    )

    stmt = select(MarketPriceSnapshot).join(
        subq,
        (MarketPriceSnapshot.condition_id == subq.c.condition_id)
        & (MarketPriceSnapshot.captured_at == subq.c.max_ts),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_snapshot_count(session: AsyncSession) -> int:
    """Return total number of price snapshots stored."""
    result = await session.execute(select(func.count()).select_from(MarketPriceSnapshot))
    return result.scalar_one()
