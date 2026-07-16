"""
Portfolio repository — Layer 10: Portfolio Reporting.

All DB query operations for cross-layer portfolio aggregations.
Read-only: no writes, no mutations.

Sources:
  Position        — open / closed positions, PnL
  Order           — filled orders, execution stats
  TradeDecision   — strategy decisions by status
  RiskEvent       — risk check results by reason
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.order import Order
from app.models.position import Position
from app.models.risk_event import RiskEvent
from app.models.trade_decision import TradeDecision

logger = get_logger(__name__)


async def get_portfolio_summary(session: AsyncSession) -> dict:
    """
    High-level portfolio snapshot.

    Returns
    -------
    dict with:
      total_positions, open_positions, closed_positions,
      total_orders, executed_orders,
      approved_decisions, blocked_decisions
    """
    pos_counts = await session.execute(
        select(Position.status, func.count().label("cnt"))
        .group_by(Position.status)
    )
    by_pos_status: dict[str, int] = {r[0]: r[1] for r in pos_counts.all()}

    ord_counts = await session.execute(
        select(Order.status, func.count().label("cnt"))
        .group_by(Order.status)
    )
    by_ord_status: dict[str, int] = {r[0]: r[1] for r in ord_counts.all()}

    td_counts = await session.execute(
        select(TradeDecision.status, func.count().label("cnt"))
        .group_by(TradeDecision.status)
    )
    by_td_status: dict[str, int] = {r[0]: r[1] for r in td_counts.all()}

    total_positions = sum(by_pos_status.values())
    total_orders = sum(by_ord_status.values())

    return {
        "total_positions": total_positions,
        "open_positions": by_pos_status.get("OPEN", 0),
        "closed_positions": by_pos_status.get("CLOSED", 0),
        "total_orders": total_orders,
        "executed_orders": by_ord_status.get("FILLED", 0),
        "approved_decisions": by_td_status.get("RISK_APPROVED", 0)
        + by_td_status.get("EXECUTED", 0),
        "blocked_decisions": by_td_status.get("BLOCKED", 0),
        "initial_capital": settings.CAPITAL_INITIAL_USDC,
    }


async def get_position_summary(session: AsyncSession) -> dict:
    """
    Position breakdown by status, asset, and side.

    Returns
    -------
    dict with:
      total_positions, open_positions, closed_positions,
      by_asset (dict[str, int]), by_side (dict[str, int])
    """
    pos_counts = await session.execute(
        select(Position.status, func.count().label("cnt"))
        .group_by(Position.status)
    )
    by_status: dict[str, int] = {r[0]: r[1] for r in pos_counts.all()}

    asset_counts = await session.execute(
        select(Position.asset, func.count().label("cnt"))
        .group_by(Position.asset)
    )
    by_asset: dict[str, int] = {r[0]: r[1] for r in asset_counts.all()}

    side_counts = await session.execute(
        select(Position.side, func.count().label("cnt"))
        .group_by(Position.side)
    )
    by_side: dict[str, int] = {r[0]: r[1] for r in side_counts.all()}

    total = sum(by_status.values())

    return {
        "total_positions": total,
        "open_positions": by_status.get("OPEN", 0),
        "closed_positions": by_status.get("CLOSED", 0),
        "by_asset": by_asset,
        "by_side": by_side,
    }


async def get_order_summary(session: AsyncSession) -> dict:
    """
    Order breakdown by status and asset.

    Returns
    -------
    dict with:
      total_orders, filled_orders, pending_orders,
      by_asset (dict[str, int]), by_side (dict[str, int])
    """
    status_counts = await session.execute(
        select(Order.status, func.count().label("cnt"))
        .group_by(Order.status)
    )
    by_status: dict[str, int] = {r[0]: r[1] for r in status_counts.all()}

    asset_counts = await session.execute(
        select(Order.asset, func.count().label("cnt"))
        .group_by(Order.asset)
    )
    by_asset: dict[str, int] = {r[0]: r[1] for r in asset_counts.all()}

    side_counts = await session.execute(
        select(Order.side, func.count().label("cnt"))
        .group_by(Order.side)
    )
    by_side: dict[str, int] = {r[0]: r[1] for r in side_counts.all()}

    total = sum(by_status.values())

    return {
        "total_orders": total,
        "filled_orders": by_status.get("FILLED", 0),
        "pending_orders": by_status.get("PENDING", 0),
        "by_asset": by_asset,
        "by_side": by_side,
    }


async def get_risk_summary(session: AsyncSession) -> dict:
    """
    Risk check breakdown from RiskEvent records.

    Returns
    -------
    dict with:
      total_checked, allowed, blocked, block_rate_pct,
      by_reason (dict[str, int])
    """
    result_counts = await session.execute(
        select(RiskEvent.result, func.count().label("cnt"))
        .group_by(RiskEvent.result)
    )
    by_result: dict[str, int] = {r[0]: r[1] for r in result_counts.all()}

    reason_counts = await session.execute(
        select(RiskEvent.reason, func.count().label("cnt"))
        .where(
            RiskEvent.result == "BLOCK",
            RiskEvent.reason.is_not(None),
        )
        .group_by(RiskEvent.reason)
    )
    by_reason: dict[str, int] = {r[0]: r[1] for r in reason_counts.all()}

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


async def get_pnl_summary(session: AsyncSession) -> dict:
    """
    PnL aggregates from Position records.

    Returns
    -------
    dict with:
      open_positions, total_unrealized_pnl, average_unrealized_pnl,
      closed_positions, total_realized_pnl
    """
    # Unrealized PnL spans both OPEN and PARTIAL lots — a PARTIAL lot still
    # has remaining_quantity in the market and continues to accrue unrealized PnL.
    # Excluding PARTIAL here understates total_live_state and breaks Cumulative Outcome.
    unrealized_row = await session.execute(
        select(
            func.count(Position.id).label("cnt"),
            func.coalesce(func.sum(Position.unrealized_pnl), 0.0).label("total"),
            func.coalesce(func.avg(Position.unrealized_pnl), 0.0).label("avg"),
        )
        .where(
            Position.status.in_(["OPEN", "PARTIAL"]),
            Position.unrealized_pnl.is_not(None),
        )
    )
    u = unrealized_row.one()

    # Resolution Result = SUM of realized_pnl for ALL positions that have
    # realized something: both fully CLOSED lots and still-open PARTIAL lots
    # (which accumulate realized_pnl from each partial exit slice).
    realized_row = await session.execute(
        select(
            func.count(Position.id).label("cnt"),
            func.coalesce(func.sum(Position.realized_pnl), 0.0).label("total"),
        )
        .where(
            Position.status.in_(["CLOSED", "PARTIAL"]),
            Position.realized_pnl.is_not(None),
        )
    )
    r = realized_row.one()

    return {
        "open_positions": int(u.cnt),
        "total_unrealized_pnl": round(float(u.total), 6),
        "average_unrealized_pnl": round(float(u.avg), 6),
        "closed_positions": int(r.cnt),
        "total_realized_pnl": round(float(r.total), 6),
    }
