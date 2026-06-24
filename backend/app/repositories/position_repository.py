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
) -> Position:
    """Insert a new OPEN position row and return it."""
    now = datetime.now(timezone.utc)
    row = Position(
        order_id=order_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        current_price=None,
        unrealized_pnl=None,
        realized_pnl=None,
        status="OPEN",
        opened_at=opened_at or now,
        closed_at=None,
    )
    session.add(row)
    logger.debug(
        "Position created",
        order_id=order_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        entry_price=entry_price,
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
    """Return all OPEN positions ordered by opened_at ascending."""
    stmt = (
        select(Position)
        .where(Position.status == "OPEN")
        .order_by(Position.opened_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


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
    """Return sum(quantity * entry_price) across all OPEN positions."""
    result = await session.execute(
        select(func.coalesce(func.sum(Position.quantity * Position.entry_price), 0.0))
        .where(Position.status == "OPEN")
    )
    return float(result.scalar_one() or 0.0)


async def get_asset_open_exposure(session: AsyncSession, asset: str) -> float:
    """Return sum(quantity * entry_price) for OPEN positions on a given asset."""
    result = await session.execute(
        select(func.coalesce(func.sum(Position.quantity * Position.entry_price), 0.0))
        .where(Position.status == "OPEN", Position.asset == asset)
    )
    return float(result.scalar_one() or 0.0)


async def get_open_position_count(session: AsyncSession) -> int:
    """Return the count of OPEN positions."""
    result = await session.execute(
        select(func.count(Position.id)).where(Position.status == "OPEN")
    )
    return int(result.scalar_one() or 0)


async def get_open_position_count_by_timeframe(
    session: AsyncSession, timeframe: str
) -> int:
    """Return the count of OPEN positions for a given timeframe."""
    result = await session.execute(
        select(func.count(Position.id))
        .where(Position.status == "OPEN", Position.timeframe == timeframe)
    )
    return int(result.scalar_one() or 0)


async def get_position_stats(session: AsyncSession) -> dict:
    """Return aggregate position statistics."""
    status_result = await session.execute(
        select(Position.status, func.count().label("cnt"))
        .group_by(Position.status)
    )
    counts: dict[str, int] = {r[0]: r[1] for r in status_result.all()}

    pnl_result = await session.execute(
        select(
            func.sum(Position.unrealized_pnl).label("total_unrealized"),
            func.sum(Position.realized_pnl).label("total_realized"),
            func.avg(Position.unrealized_pnl).label("avg_unrealized"),
        ).where(Position.status == "OPEN")
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
