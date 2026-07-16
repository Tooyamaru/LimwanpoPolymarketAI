"""
Risk repository — Layer 9: Risk Engine.

All DB persistence and query operations for the `risk_events` table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.risk_event import RiskEvent

logger = get_logger(__name__)


async def create_risk_event(
    session: AsyncSession,
    *,
    decision_id: int,
    condition_id: str,
    asset: str,
    timeframe: str,
    result: str,
    reason: Optional[str] = None,
    open_positions_count: int = 0,
    daily_loss: float = 0.0,
    daily_trades: int = 0,
    checked_at: Optional[datetime] = None,
) -> RiskEvent:
    """Append a new RiskEvent row and return the persisted object."""
    if checked_at is None:
        checked_at = datetime.now(timezone.utc)

    row = RiskEvent(
        decision_id=decision_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        result=result,
        reason=reason,
        checked_at=checked_at,
        open_positions_count=open_positions_count,
        daily_loss=round(daily_loss, 6),
        daily_trades=daily_trades,
    )
    session.add(row)

    logger.debug(
        "Risk event created",
        decision_id=decision_id,
        asset=asset,
        timeframe=timeframe,
        result=result,
        reason=reason,
    )
    return row


async def get_risk_events(
    session: AsyncSession,
    result_filter: Optional[str] = None,
    limit: int = 100,
) -> list[RiskEvent]:
    """Return recent risk events, newest first. Optionally filter by result."""
    stmt = select(RiskEvent)
    if result_filter:
        stmt = stmt.where(RiskEvent.result == result_filter)
    stmt = stmt.order_by(desc(RiskEvent.checked_at)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_blocked_events(
    session: AsyncSession,
    limit: int = 100,
) -> list[RiskEvent]:
    """Return BLOCK events, newest first."""
    stmt = (
        select(RiskEvent)
        .where(RiskEvent.result == "BLOCK")
        .order_by(desc(RiskEvent.checked_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_risk_stats(session: AsyncSession) -> dict:
    """Return aggregate counts broken down by result and reason."""
    result_counts = await session.execute(
        select(RiskEvent.result, func.count().label("cnt"))
        .group_by(RiskEvent.result)
    )
    by_result = {r[0]: r[1] for r in result_counts.all()}

    reason_counts = await session.execute(
        select(RiskEvent.reason, func.count().label("cnt"))
        .where(RiskEvent.result == "BLOCK", RiskEvent.reason.is_not(None))
        .group_by(RiskEvent.reason)
    )
    by_reason = {r[0]: r[1] for r in reason_counts.all()}

    total = sum(by_result.values())
    allowed = by_result.get("ALLOW", 0)
    blocked = by_result.get("BLOCK", 0)
    block_rate = round((blocked / total * 100) if total > 0 else 0.0, 1)

    return {
        "total_checked": total,
        "allowed": allowed,
        "blocked": blocked,
        "block_rate_pct": block_rate,
        "by_reason": by_reason,
    }
