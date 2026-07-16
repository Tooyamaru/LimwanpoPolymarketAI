"""
Live Trades router — read-only aggregation of real executed trade events.

GET /live-trades    — newest-first stream of ENTRY / SCALE_IN / PARTIAL_EXIT /
                      FINAL_EXIT / EXPIRY_EXIT events from orders + positions.

Rules:
- Only FILLED orders are included.
- WAIT / BLOCKED / REJECTED / PENDING are never surfaced.
- event_type is derived from order side + position entry_sequence + close_reason.
- Read-only: never triggers execution, never creates orders or positions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.order import Order
from app.models.position import Position

logger = get_logger(__name__)

router = APIRouter(prefix="/live-trades", tags=["live-trades"])


def _derive_event_type(order: Order, pos: Optional[Position]) -> str:
    """
    Derive a human-readable event type from order + position context.

    Entry orders (LONG_YES / LONG_NO):
      entry_sequence == 1  → ENTRY
      entry_sequence >  1  → SCALE_IN
      no position linked   → ENTRY  (fallback)

    Exit orders (SELL_YES / SELL_NO):
      close_reason contains EXPIRY → EXPIRY_EXIT
      position fully closed        → FINAL_EXIT
      position still partially open→ PARTIAL_EXIT
    """
    if order.side in ("LONG_YES", "LONG_NO"):
        if pos and pos.entry_sequence and pos.entry_sequence > 1:
            return "SCALE_IN"
        return "ENTRY"

    # Exit order
    if pos:
        reason = (pos.close_reason or "").upper()
        if "EXPIRY" in reason:
            return "EXPIRY_EXIT"
        remaining = pos.remaining_quantity or 0.0
        if remaining <= 1e-9:
            return "FINAL_EXIT"
        return "PARTIAL_EXIT"

    return "FINAL_EXIT"   # fallback for exit with no position link


@router.get("")
async def get_live_trades(
    limit: int = Query(default=50, ge=1, le=200),
    asset: Optional[str] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
    condition_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Return real executed trade events, newest first.

    Sourced exclusively from FILLED orders.  WAIT / BLOCKED / PENDING are
    never included.  event_type is one of:
      ENTRY | SCALE_IN | PARTIAL_EXIT | FINAL_EXIT | EXPIRY_EXIT
    """
    stmt = (
        select(Order)
        .where(Order.status == "FILLED")
        .where(Order.side.in_(["LONG_YES", "LONG_NO", "SELL_YES", "SELL_NO"]))
        .order_by(desc(Order.filled_at))
        .limit(limit * 3)   # over-fetch to allow post-filter
    )
    if asset:
        stmt = stmt.where(Order.asset == asset.upper())
    if timeframe:
        stmt = stmt.where(Order.timeframe == timeframe.lower())
    if condition_id:
        stmt = stmt.where(Order.condition_id == condition_id)

    orders = list((await session.execute(stmt)).scalars().all())

    # Load linked positions in bulk (by order id via close_order_id or decision_id)
    order_ids = [o.id for o in orders]
    pos_by_order: dict[int, Position] = {}
    if order_ids:
        # entry positions: opened_at aligns with order filled_at; match via decision_id
        pos_stmt = select(Position).where(
            Position.condition_id.in_([o.condition_id for o in orders])
        )
        all_pos = list((await session.execute(pos_stmt)).scalars().all())
        # Index: close_order_id → position (exit link)
        for p in all_pos:
            if p.close_order_id and p.close_order_id in set(order_ids):
                pos_by_order[p.close_order_id] = p
        # Index: condition_id → lowest entry_sequence position (entry link)
        entry_pos_by_cid: dict[str, list[Position]] = {}
        for p in all_pos:
            entry_pos_by_cid.setdefault(p.condition_id, []).append(p)

    events = []
    for order in orders:
        is_entry = order.side in ("LONG_YES", "LONG_NO")

        pos: Optional[Position] = None
        if is_entry:
            # For entry orders: find the position with matching condition_id
            # opened closest in time (best-effort link without explicit FK)
            candidates = entry_pos_by_cid.get(order.condition_id, [])
            if candidates:
                pos = min(candidates, key=lambda p: abs(
                    (p.opened_at - order.filled_at).total_seconds()
                    if p.opened_at and order.filled_at else 9999
                ))
        else:
            pos = pos_by_order.get(order.id)

        et = _derive_event_type(order, pos)

        # Post-filter by event_type
        if event_type and et != event_type.upper():
            continue

        # Side label: YES or NO (strip LONG_ / SELL_ prefix)
        side_label = "YES" if order.side in ("LONG_YES", "SELL_YES") else "NO"

        realized_pnl: Optional[float] = None
        remaining_qty: Optional[float] = None
        if pos and not is_entry:
            realized_pnl = float(pos.realized_pnl or 0.0)
            remaining_qty = float(pos.remaining_quantity or 0.0)

        events.append({
            "event_id": order.id,
            "event_type": et,
            "timestamp": order.filled_at.isoformat() if order.filled_at else None,
            "asset": order.asset,
            "timeframe": order.timeframe,
            "condition_id": order.condition_id,
            "side": side_label,
            "quantity": float(order.quantity or 0),
            "price": float(order.filled_price or 0),
            "notional_usdc": round(
                float(order.filled_price or 0) * float(order.quantity or 0), 4
            ),
            "realized_pnl": realized_pnl,
            "remaining_quantity": remaining_qty,
            "exit_reason": pos.close_reason if (pos and not is_entry) else None,
            "lot_id": pos.id if pos else None,
            "order_id": order.id,
            "decision_id": order.decision_id,
            "status": order.status,
        })

        if len(events) >= limit:
            break

    return events
