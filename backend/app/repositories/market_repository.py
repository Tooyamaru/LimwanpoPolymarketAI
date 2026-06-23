"""
Market repository — database persistence layer.

All DB operations go through this module; no raw SQL in collectors or API handlers.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market import Market
from app.models.market_snapshot import MarketSnapshot

logger = get_logger(__name__)


async def save_market(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    polymarket_market_id: str,
    title: str,
    end_time: Optional[datetime] = None,
    start_time: Optional[datetime] = None,
    status: str = "active",
) -> Market:
    """
    Upsert a market record.

    If a market with the same polymarket_market_id already exists it is returned
    as-is. Otherwise a new row is inserted.
    """
    stmt = select(Market).where(Market.polymarket_market_id == polymarket_market_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    market = Market(
        asset=asset,
        timeframe=timeframe,
        polymarket_market_id=polymarket_market_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        status=status,
    )
    session.add(market)
    await session.flush()  # populate market.id without committing
    logger.info("New market inserted", asset=asset, timeframe=timeframe, market_id=polymarket_market_id)
    return market


async def update_market(
    session: AsyncSession,
    polymarket_market_id: str,
    *,
    status: Optional[str] = None,
    end_time: Optional[datetime] = None,
    title: Optional[str] = None,
) -> Optional[Market]:
    """
    Update mutable fields on an existing market.
    Returns the updated market or None if not found.
    """
    values: dict = {}
    if status is not None:
        values["status"] = status
    if end_time is not None:
        values["end_time"] = end_time
    if title is not None:
        values["title"] = title

    if not values:
        return None

    stmt = (
        update(Market)
        .where(Market.polymarket_market_id == polymarket_market_id)
        .values(**values)
        .returning(Market)
    )
    result = await session.execute(stmt)
    market = result.scalar_one_or_none()
    if market:
        logger.debug("Market updated", market_id=polymarket_market_id, fields=list(values.keys()))
    return market


async def save_snapshot(
    session: AsyncSession,
    *,
    market_id: int,
    timestamp: datetime,
    yes_price: Optional[float] = None,
    no_price: Optional[float] = None,
    liquidity: Optional[float] = None,
    volume: Optional[float] = None,
    binance_price: Optional[float] = None,
) -> MarketSnapshot:
    """
    Append a new snapshot row for a market.
    """
    snapshot = MarketSnapshot(
        market_id=market_id,
        timestamp=timestamp,
        yes_price=yes_price,
        no_price=no_price,
        liquidity=liquidity,
        volume=volume,
        binance_price=binance_price,
    )
    session.add(snapshot)
    await session.flush()
    logger.debug("Snapshot saved", market_id=market_id, ts=timestamp.isoformat())
    return snapshot


async def get_active_markets(session: AsyncSession) -> list[Market]:
    """Return all markets with status = 'active'."""
    result = await session.execute(
        select(Market).where(Market.status == "active").order_by(Market.asset, Market.timeframe)
    )
    return list(result.scalars().all())


async def get_latest_snapshots(
    session: AsyncSession, limit: int = 50
) -> list[MarketSnapshot]:
    """Return the most recent snapshots across all markets."""
    result = await session.execute(
        select(MarketSnapshot)
        .order_by(MarketSnapshot.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
