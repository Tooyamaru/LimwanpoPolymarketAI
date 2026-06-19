"""
Universe repository — database persistence layer for market_universe.

All DB operations for the MarketUniverse table go through this module.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse

logger = get_logger(__name__)


# ── Write operations ───────────────────────────────────────────────────────────

async def upsert_universe_market(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    series_slug: str,
    series_id: Optional[str],
    event_id: Optional[str],
    condition_id: str,
    yes_token_id: Optional[str],
    no_token_id: Optional[str],
    question: str,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    status: str,
) -> MarketUniverse:
    """
    Insert or update a MarketUniverse row identified by condition_id.

    If the row already exists, mutable fields (status, end_time, updated_at)
    are refreshed.  Returns the final row.
    """
    stmt = select(MarketUniverse).where(MarketUniverse.condition_id == condition_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.status = status
        if end_time is not None:
            existing.end_time = end_time
        if yes_token_id is not None:
            existing.yes_token_id = yes_token_id
        if no_token_id is not None:
            existing.no_token_id = no_token_id
        existing.updated_at = datetime.now(timezone.utc)
        await session.flush()
        logger.debug("Universe market updated", condition_id=condition_id, status=status)
        return existing

    market = MarketUniverse(
        asset=asset,
        timeframe=timeframe,
        series_slug=series_slug,
        series_id=series_id,
        event_id=event_id,
        condition_id=condition_id,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        question=question,
        start_time=start_time,
        end_time=end_time,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(market)
    await session.flush()
    logger.info(
        "Universe market inserted",
        asset=asset,
        timeframe=timeframe,
        series_slug=series_slug,
        condition_id=condition_id,
        status=status,
    )
    return market


async def demote_excess_active_markets(
    session: AsyncSession,
    asset: str,
    timeframe: str,
    keep_condition_id: Optional[str],
) -> int:
    """
    Sprint 9.1 — enforce the "exactly one active per (asset, timeframe)" invariant.

    After sync has determined which condition_id is the true active market for
    a series, call this function to downgrade every OTHER active record for the
    same (asset, timeframe) to "upcoming".

    This handles stale records that were inserted as "active" in a previous sync
    cycle but whose condition_ids are no longer returned by the current
    fetch_events call (e.g. old windows that fell off the top-20 page but whose
    end_time is still in the future, so expire_stale_markets() cannot touch them).

    Args:
        session:           The current async session (inside an open transaction).
        asset:             Asset identifier, e.g. "BTC".
        timeframe:         Timeframe string, e.g. "5m".
        keep_condition_id: The condition_id that must STAY active.
                           Pass None when there is no active market for this series
                           (e.g. all markets expired) — demotes all active rows.

    Returns:
        Number of rows demoted from "active" → "upcoming".
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(MarketUniverse)
        .where(
            MarketUniverse.asset == asset,
            MarketUniverse.timeframe == timeframe,
            MarketUniverse.status == "active",
            MarketUniverse.condition_id != keep_condition_id
            if keep_condition_id
            else True,
        )
        .values(status="upcoming", updated_at=now)
    )
    result = await session.execute(stmt)
    count = result.rowcount
    if count:
        logger.info(
            "Demoted excess active markets to upcoming",
            asset=asset,
            timeframe=timeframe,
            kept=keep_condition_id,
            demoted=count,
        )
    return count


async def expire_stale_markets(session: AsyncSession) -> int:
    """
    Mark any active/upcoming market whose end_time is in the past as expired.
    Returns the number of rows updated.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(MarketUniverse)
        .where(
            MarketUniverse.status.in_(["active", "upcoming"]),
            MarketUniverse.end_time != None,  # noqa: E711
            MarketUniverse.end_time < now,
        )
        .values(status="expired", updated_at=now)
    )
    result = await session.execute(stmt)
    count = result.rowcount
    if count:
        logger.info("Stale universe markets expired", count=count)
    return count


# ── Read operations ────────────────────────────────────────────────────────────

async def get_active_universe(session: AsyncSession) -> list[MarketUniverse]:
    """Return all markets with status = 'active'."""
    result = await session.execute(
        select(MarketUniverse)
        .where(MarketUniverse.status == "active")
        .order_by(MarketUniverse.asset, MarketUniverse.timeframe)
    )
    return list(result.scalars().all())


async def get_upcoming_universe(session: AsyncSession) -> list[MarketUniverse]:
    """Return all markets with status = 'upcoming'."""
    result = await session.execute(
        select(MarketUniverse)
        .where(MarketUniverse.status == "upcoming")
        .order_by(MarketUniverse.asset, MarketUniverse.timeframe, MarketUniverse.start_time)
    )
    return list(result.scalars().all())


async def get_all_universe(session: AsyncSession) -> list[MarketUniverse]:
    """Return every market_universe row."""
    result = await session.execute(
        select(MarketUniverse).order_by(
            MarketUniverse.asset,
            MarketUniverse.timeframe,
            MarketUniverse.start_time,
        )
    )
    return list(result.scalars().all())


async def get_universe_by_series(
    session: AsyncSession, series_slug: str
) -> list[MarketUniverse]:
    """Return all rows for a specific series slug."""
    result = await session.execute(
        select(MarketUniverse)
        .where(MarketUniverse.series_slug == series_slug)
        .order_by(MarketUniverse.start_time)
    )
    return list(result.scalars().all())


async def get_universe_stats(session: AsyncSession) -> dict:
    """
    Build the statistics dict required by GET /api/v1/universe/stats.

    Returns counts broken down by asset × timeframe × status.
    """
    assets = ["BTC", "ETH", "SOL", "XRP"]
    timeframes = ["5m", "15m", "1H"]
    statuses = ["active", "upcoming", "expired"]

    rows = await get_all_universe(session)

    stats: dict = {
        "total": len(rows),
        "by_status": {s: 0 for s in statuses},
        "by_asset": {},
        "by_timeframe": {},
    }

    for asset in assets:
        stats["by_asset"][asset] = {
            "total": 0,
            "by_timeframe": {tf: {s: 0 for s in statuses} for tf in timeframes},
        }

    for tf in timeframes:
        stats["by_timeframe"][tf] = {s: 0 for s in statuses}

    for row in rows:
        s = row.status if row.status in statuses else "expired"
        stats["by_status"][s] = stats["by_status"].get(s, 0) + 1

        if row.asset in stats["by_asset"]:
            stats["by_asset"][row.asset]["total"] += 1
            tf_key = row.timeframe if row.timeframe in timeframes else row.timeframe
            if tf_key in stats["by_asset"][row.asset]["by_timeframe"]:
                stats["by_asset"][row.asset]["by_timeframe"][tf_key][s] = (
                    stats["by_asset"][row.asset]["by_timeframe"][tf_key].get(s, 0) + 1
                )

        if row.timeframe in stats["by_timeframe"]:
            stats["by_timeframe"][row.timeframe][s] = (
                stats["by_timeframe"][row.timeframe].get(s, 0) + 1
            )

    return stats
