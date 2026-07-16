"""
Position repository — Layer 8: Position Tracking.

All DB persistence and query operations for the `positions` table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.position import Position

logger = get_logger(__name__)

# Statuses that still carry unclosed exposure — a lot is "open" for risk /
# exit / exposure purposes until every unit has been closed out.
OPEN_LIKE_STATUSES = ("OPEN", "PARTIAL")


async def create_position(
    session: AsyncSession,
    *,
    order_id: int,
    condition_id: str,
    asset: str,
    timeframe: str,
    side: str,
    quantity: float,
    entry_price: float,
    opened_at: Optional[datetime] = None,
    total_fee_usdc: Optional[float] = None,
    entry_sequence: int = 1,
    scale_in_reason: Optional[str] = None,
) -> Position:
    """Insert a new OPEN position ("lot") row and return it."""
    now = datetime.now(timezone.utc)
    row = Position(
        order_id=order_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        quantity=quantity,
        remaining_quantity=quantity,
        entry_price=entry_price,
        current_price=None,
        unrealized_pnl=None,
        realized_pnl=None,
        peak_pnl_usdc=None,
        total_fee_usdc=total_fee_usdc or 0.0,
        status="OPEN",
        opened_at=opened_at or now,
        closed_at=None,
        entry_sequence=entry_sequence,
        scale_in_reason=scale_in_reason,
    )
    session.add(row)
    logger.debug(
        "Position created",
        order_id=order_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        entry_price=entry_price,
        total_fee_usdc=total_fee_usdc,
        entry_sequence=entry_sequence,
        scale_in_reason=scale_in_reason,
    )
    return row


async def get_position(
    session: AsyncSession,
    position_id: int,
) -> Optional[Position]:
    """Return a single position by primary key."""
    result = await session.execute(
        select(Position).where(Position.id == position_id)
    )
    return result.scalar_one_or_none()


async def get_positions(
    session: AsyncSession,
    status_filter: Optional[str] = None,
    limit: int = 200,
) -> list[Position]:
    """Return positions, newest first. Optionally filter by status."""
    stmt = select(Position)
    if status_filter:
        stmt = stmt.where(Position.status == status_filter)
    stmt = stmt.order_by(desc(Position.opened_at)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_open_positions(
    session: AsyncSession,
    limit: int = 500,
) -> list[Position]:
    """Return all still-open lots (status OPEN or PARTIAL), opened_at ascending."""
    stmt = (
        select(Position)
        .where(Position.status.in_(OPEN_LIKE_STATUSES))
        .order_by(Position.opened_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_positions_for_condition(
    session: AsyncSession,
    condition_id: str,
    only_open: bool = False,
) -> list[Position]:
    """Return every lot for a condition_id, oldest first. Optionally OPEN/PARTIAL only."""
    stmt = select(Position).where(Position.condition_id == condition_id)
    if only_open:
        stmt = stmt.where(Position.status.in_(OPEN_LIKE_STATUSES))
    stmt = stmt.order_by(Position.opened_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_lifetime_entry_count(session: AsyncSession, condition_id: str) -> int:
    """Return the total number of lots (entries) ever opened for a condition_id."""
    result = await session.execute(
        select(func.count(Position.id)).where(Position.condition_id == condition_id)
    )
    return int(result.scalar_one() or 0)


async def get_position_by_order(
    session: AsyncSession,
    order_id: int,
) -> Optional[Position]:
    """Return the position linked to a specific order_id."""
    result = await session.execute(
        select(Position).where(Position.order_id == order_id)
    )
    return result.scalar_one_or_none()


async def get_closed_positions(session: AsyncSession) -> list[Position]:
    """Return all CLOSED positions ordered by closed_at ascending (for equity curve)."""
    result = await session.execute(
        select(Position)
        .where(Position.status == "CLOSED")
        .order_by(Position.closed_at)
    )
    return list(result.scalars().all())


async def get_total_open_exposure(session: AsyncSession) -> float:
    """Return sum(remaining_quantity * entry_price) across all open lots."""
    result = await session.execute(
        select(func.coalesce(func.sum(Position.remaining_quantity * Position.entry_price), 0.0))
        .where(Position.status.in_(OPEN_LIKE_STATUSES))
    )
    return float(result.scalar_one() or 0.0)


async def get_asset_open_exposure(session: AsyncSession, asset: str) -> float:
    """Return sum(remaining_quantity * entry_price) for open lots on a given asset."""
    result = await session.execute(
        select(func.coalesce(func.sum(Position.remaining_quantity * Position.entry_price), 0.0))
        .where(Position.status.in_(OPEN_LIKE_STATUSES), Position.asset == asset)
    )
    return float(result.scalar_one() or 0.0)


async def get_condition_open_exposure(session: AsyncSession, condition_id: str) -> float:
    """Return sum(remaining_quantity * entry_price) for open lots in one market."""
    result = await session.execute(
        select(func.coalesce(func.sum(Position.remaining_quantity * Position.entry_price), 0.0))
        .where(Position.status.in_(OPEN_LIKE_STATUSES), Position.condition_id == condition_id)
    )
    return float(result.scalar_one() or 0.0)


async def get_open_position_count(session: AsyncSession) -> int:
    """Return the count of open lots (OPEN or PARTIAL)."""
    result = await session.execute(
        select(func.count(Position.id)).where(Position.status.in_(OPEN_LIKE_STATUSES))
    )
    return int(result.scalar_one() or 0)


async def get_open_position_count_by_timeframe(
    session: AsyncSession, timeframe: str
) -> int:
    """Return the count of open lots for a given timeframe."""
    result = await session.execute(
        select(func.count(Position.id))
        .where(Position.status.in_(OPEN_LIKE_STATUSES), Position.timeframe == timeframe)
    )
    return int(result.scalar_one() or 0)


async def get_position_stats(session: AsyncSession) -> dict:
    """Return aggregate position statistics."""
    status_result = await session.execute(
        select(Position.status, func.count().label("cnt"))
        .group_by(Position.status)
    )
    counts: dict[str, int] = {r[0]: r[1] for r in status_result.all()}

    # PARTIAL lots still hold open contracts and carry unrealized PnL;
    # exclude them and the total is understated after any partial exit.
    pnl_result = await session.execute(
        select(
            func.sum(Position.unrealized_pnl).label("total_unrealized"),
            func.sum(Position.realized_pnl).label("total_realized"),
            func.avg(Position.unrealized_pnl).label("avg_unrealized"),
        ).where(Position.status.in_(OPEN_LIKE_STATUSES))
    )
    pnl_row = pnl_result.one()

    total = sum(counts.values())
    return {
        "total_positions": total,
        "open": counts.get("OPEN", 0),
        "closed": counts.get("CLOSED", 0),
        "total_unrealized_pnl": round(float(pnl_row.total_unrealized or 0), 6),
        "total_realized_pnl": round(float(pnl_row.total_realized or 0), 6),
        "avg_unrealized_pnl": round(float(pnl_row.avg_unrealized or 0), 6),
    }
