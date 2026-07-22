"""
Order repository — Layer 7: Execution Engine (Paper Mode).

All DB persistence and query operations for the `orders` table.
Orders are append-only — no UPSERTs.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.order import Order

logger = get_logger(__name__)


async def create_order(
    session: AsyncSession,
    *,
    decision_id: int,
    condition_id: str,
    asset: str,
    timeframe: str,
    side: str,
    order_type: str = "MARKET",
    quantity: float = 1.0,
    requested_price: Optional[float],
    filled_price: Optional[float],
    status: str = "FILLED",
    created_at: Optional[datetime] = None,
    filled_at: Optional[datetime] = None,
    entry_fee_usdc: Optional[float] = None,
    exit_fee_usdc: Optional[float] = None,
    # 14A2A: exact token traceability — optional for backward compatibility
    token_id: Optional[str] = None,
    price_source: Optional[str] = None,
    clob_fetched_at: Optional[datetime] = None,
) -> Order:
    """Insert a new order row and return the persisted object."""
    now = datetime.now(timezone.utc)
    row = Order(
        decision_id=decision_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        order_type=order_type,
        quantity=quantity,
        requested_price=requested_price,
        filled_price=filled_price,
        status=status,
        created_at=created_at or now,
        filled_at=filled_at or (now if status == "FILLED" else None),
        entry_fee_usdc=entry_fee_usdc,
        exit_fee_usdc=exit_fee_usdc,
        token_id=token_id,
        price_source=price_source,
        clob_fetched_at=clob_fetched_at,
    )
    session.add(row)

    logger.debug(
        "Order created",
        asset=asset,
        timeframe=timeframe,
        side=side,
        filled_price=filled_price,
        status=status,
        entry_fee_usdc=entry_fee_usdc,
        exit_fee_usdc=exit_fee_usdc,
    )
    return row


async def get_order(
    session: AsyncSession,
    order_id: int,
) -> Optional[Order]:
    """Return a single order by primary key."""
    result = await session.execute(
        select(Order).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_orders(
    session: AsyncSession,
    status_filter: Optional[str] = None,
    limit: int = 200,
) -> list[Order]:
    """Return recent orders, newest first. Optionally filter by status."""
    stmt = select(Order)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(desc(Order.created_at)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_open_orders(
    session: AsyncSession,
    limit: int = 100,
) -> list[Order]:
    """Return orders with status PENDING (not yet filled or cancelled)."""
    stmt = (
        select(Order)
        .where(Order.status == "PENDING")
        .order_by(desc(Order.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_order_stats(session: AsyncSession) -> dict:
    """Return aggregate counts and average fill price broken down by side."""
    count_result = await session.execute(
        select(Order.status, func.count().label("cnt"))
        .group_by(Order.status)
    )
    counts: dict[str, int] = {r[0]: r[1] for r in count_result.all()}

    side_result = await session.execute(
        select(Order.side, func.count().label("cnt"), func.avg(Order.filled_price).label("avg_price"))
        .where(Order.status == "FILLED")
        .group_by(Order.side)
    )
    side_rows = side_result.all()
    side_stats: dict[str, dict] = {
        r[0]: {"count": r[1], "avg_price": round(float(r[2] or 0), 4)}
        for r in side_rows
    }

    total = sum(counts.values())
    return {
        "total_orders": total,
        "filled": counts.get("FILLED", 0),
        "pending": counts.get("PENDING", 0),
        "cancelled": counts.get("CANCELLED", 0),
        "failed": counts.get("FAILED", 0),
        "long_yes_filled": side_stats.get("LONG_YES", {}).get("count", 0),
        "long_no_filled": side_stats.get("LONG_NO", {}).get("count", 0),
        "avg_fill_price_yes": side_stats.get("LONG_YES", {}).get("avg_price", 0.0),
        "avg_fill_price_no": side_stats.get("LONG_NO", {}).get("avg_price", 0.0),
    }
