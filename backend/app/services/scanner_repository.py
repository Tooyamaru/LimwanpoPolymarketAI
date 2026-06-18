"""
Scanner repository — database persistence layer for scanner_markets.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.scanner_market import ScannerMarket

logger = get_logger(__name__)


async def save_scanner_market(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    market_id: str,
    health_status: str = "active",
    created_at: datetime,
    raw_title: str,
    matching_rule: str,
    detected_asset: str,
    detected_timeframe: str,
) -> ScannerMarket:
    """
    Upsert a scanner market record.

    If the market_id already exists, we update health_status and transparency
    fields in case the matching rule has improved. Otherwise a new row is created.
    """
    stmt = select(ScannerMarket).where(ScannerMarket.market_id == market_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.health_status = health_status
        existing.raw_title = raw_title
        existing.matching_rule = matching_rule
        existing.detected_asset = detected_asset
        existing.detected_timeframe = detected_timeframe
        return existing

    market = ScannerMarket(
        asset=asset,
        timeframe=timeframe,
        market_id=market_id,
        health_status=health_status,
        created_at=created_at,
        raw_title=raw_title,
        matching_rule=matching_rule,
        detected_asset=detected_asset,
        detected_timeframe=detected_timeframe,
    )
    session.add(market)
    await session.flush()
    logger.debug("New scanner market inserted", asset=asset, timeframe=timeframe, market_id=market_id)
    return market


async def mark_stale_markets(
    session: AsyncSession,
    active_ids: set[str],
) -> int:
    """
    Set health_status = 'stale' for any scanner_market whose market_id is NOT
    in the active_ids set returned by the latest discovery run.

    Returns the number of rows marked stale.
    """
    if not active_ids:
        return 0

    stmt = (
        select(ScannerMarket)
        .where(ScannerMarket.health_status == "active")
        .where(ScannerMarket.market_id.not_in(active_ids))
    )
    result = await session.execute(stmt)
    stale = result.scalars().all()

    count = 0
    for market in stale:
        market.health_status = "stale"
        count += 1

    if count:
        logger.info("Marked stale scanner markets", count=count)

    return count


async def get_scanner_markets(
    session: AsyncSession,
    health_status: Optional[str] = None,
) -> list[ScannerMarket]:
    """
    Return scanner markets, optionally filtered by health_status.
    Ordered by asset, then timeframe.
    """
    stmt = select(ScannerMarket).order_by(ScannerMarket.asset, ScannerMarket.timeframe)
    if health_status is not None:
        stmt = stmt.where(ScannerMarket.health_status == health_status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_scanner_stats(session: AsyncSession) -> dict:
    """Return aggregate counts for the scanner universe."""
    from sqlalchemy import func, case

    stmt = select(
        func.count().label("total"),
        func.sum(
            case((ScannerMarket.health_status == "active", 1), else_=0)
        ).label("active"),
        func.sum(
            case((ScannerMarket.health_status == "stale", 1), else_=0)
        ).label("stale"),
        func.sum(
            case((ScannerMarket.asset == "BTC", 1), else_=0)
        ).label("btc"),
        func.sum(
            case((ScannerMarket.asset == "ETH", 1), else_=0)
        ).label("eth"),
        func.sum(
            case((ScannerMarket.asset == "SOL", 1), else_=0)
        ).label("sol"),
        func.sum(
            case((ScannerMarket.asset == "XRP", 1), else_=0)
        ).label("xrp"),
    )

    result = await session.execute(stmt)
    row = result.one()

    return {
        "total": int(row.total or 0),
        "active": int(row.active or 0),
        "stale": int(row.stale or 0),
        "by_asset": {
            "BTC": int(row.btc or 0),
            "ETH": int(row.eth or 0),
            "SOL": int(row.sol or 0),
            "XRP": int(row.xrp or 0),
        },
    }
