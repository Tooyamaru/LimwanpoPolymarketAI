"""
Universe repository — database persistence layer for market_universe.

All DB operations for the MarketUniverse table go through this module.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select, update
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


async def update_market_reference(
    session: AsyncSession,
    *,
    condition_id: str,
    opening_price: Optional[float],
    opening_price_source: Optional[str],
    opening_price_timestamp: Optional[datetime],
    reference_status: str,
) -> bool:
    """
    Persist the opening_price (Price to Beat) and reference metadata for a market.

    When opening_price is non-None (a successful fetch), this performs a
    conditional update: it only writes if opening_price IS NULL in the DB,
    preventing concurrent sync runs from overwriting an already-resolved value.

    When opening_price is None (failed fetch → PENDING), it updates
    unconditionally so the status is refreshed for the next retry.

    Returns True if a row was updated, False if it was skipped (already resolved).
    """
    now = datetime.now(timezone.utc)

    if opening_price is not None:
        # Conditional update: only apply when still unresolved.
        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == condition_id,
                MarketUniverse.opening_price.is_(None),
            )
            .values(
                opening_price=opening_price,
                opening_price_source=opening_price_source,
                opening_price_timestamp=opening_price_timestamp,
                reference_status=reference_status,
                updated_at=now,
            )
        )
        result = await session.execute(stmt)
        written = result.rowcount > 0
    else:
        # Unconditional update for PENDING status refresh.
        stmt = (
            update(MarketUniverse)
            .where(MarketUniverse.condition_id == condition_id)
            .values(
                reference_status=reference_status,
                updated_at=now,
            )
        )
        result = await session.execute(stmt)
        written = result.rowcount > 0

    await session.flush()
    if written:
        logger.debug(
            "Market reference updated",
            condition_id=condition_id,
            opening_price=opening_price,
            reference_status=reference_status,
        )
    else:
        logger.debug(
            "Market reference already resolved — skipped",
            condition_id=condition_id,
        )
    return written


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


async def retire_non_catalog_timeframes(
    session: AsyncSession,
    enabled_timeframe: str,
) -> int:
    """
    5M-ONLY cleanup: demote any 'active' or 'upcoming' market whose timeframe
    is NOT in the active catalog to 'expired'.

    Called once per sync cycle so that legacy 15m/1H universe rows (which still
    have future end_times and therefore survive expire_stale_markets()) are
    immediately retired when the SERIES_CATALOG no longer includes them.

    Portfolio Coverage and the Exit Engine are unaffected — they work from the
    positions table, not from market_universe status.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(MarketUniverse)
        .where(
            MarketUniverse.timeframe != enabled_timeframe,
            MarketUniverse.status.in_(["active", "upcoming"]),
        )
        .values(status="expired", updated_at=now)
    )
    result = await session.execute(stmt)
    count = result.rowcount
    if count:
        logger.info(
            "Retired non-catalog universe markets",
            enabled_timeframe=enabled_timeframe,
            retired=count,
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
    """Return markets with status='active' that are within their live trading window.

    Secondary time guards prevent pre-market or stale-expired markets from leaking
    into the active set when the universe sync hasn't run recently:
      - start_time <= now  (market window has opened)
      - end_time   >  now  (market window has not closed)

    Markets with NULL timestamps pass through so legacy rows are not silently dropped.
    The canonical lifecycle function (get_market_lifecycle_state) performs the
    authoritative check for any subsequent enforcement steps.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(MarketUniverse)
        .where(
            MarketUniverse.status == "active",
            or_(MarketUniverse.start_time.is_(None), MarketUniverse.start_time <= now),
            or_(MarketUniverse.end_time.is_(None), MarketUniverse.end_time > now),
        )
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
