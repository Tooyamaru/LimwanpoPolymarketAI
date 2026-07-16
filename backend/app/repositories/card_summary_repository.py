"""
Card-summary repository — aggregates Position + Order rows per condition_id
for the dashboard market-card PNL / IN / OUT / LOTS display (multi-entry aware).

IN  = filled entry orders  (side LONG_YES / LONG_NO)
OUT = filled exit orders   (side SELL_YES / SELL_NO)

Both counts and notionals are read straight from the append-only `orders`
table so they reflect every fill exactly once, independent of how many lots
or partial closes are involved.

Returns one row for EVERY active condition_id passed.  Markets with no
positions return a zero-filled row (has_position=False, total_pnl=None).
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.position import Position
from app.repositories.position_repository import OPEN_LIKE_STATUSES


async def get_card_summaries(
    session: AsyncSession,
    active_markets: Optional[list[dict]] = None,
) -> dict[str, dict]:
    """
    Return {condition_id: aggregate dict} for the provided active markets.

    `active_markets` is a list of dicts with keys: condition_id, asset, timeframe.
    Every condition_id in active_markets gets a row; markets with no positions
    receive zero-filled dicts (has_position=False, total_pnl=None).

    If active_markets is None/empty the function still queries all positions
    (backward-compatible with tests that don't pass an active list).
    """
    active_cids: list[str] = []
    meta: dict[str, dict] = {}   # condition_id → {asset, timeframe}
    if active_markets:
        for m in active_markets:
            cid = m["condition_id"]
            active_cids.append(cid)
            meta[cid] = {"asset": m.get("asset"), "timeframe": m.get("timeframe")}

    # -- Query positions (lots) -----------------------------------------------
    pos_stmt = select(Position)
    if active_cids:
        pos_stmt = pos_stmt.where(Position.condition_id.in_(active_cids))
    pos_rows = list((await session.execute(pos_stmt)).scalars().all())

    # condition_ids that actually have positions
    all_condition_ids = list({p.condition_id for p in pos_rows})

    # -- IN: entry fills -------------------------------------------------------
    in_map: dict[str, dict] = {}
    if all_condition_ids:
        in_stmt = (
            select(
                Order.condition_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.filled_price * Order.quantity), 0.0),
                func.max(Order.filled_at),
            )
            .where(
                Order.condition_id.in_(all_condition_ids),
                Order.side.in_(["LONG_YES", "LONG_NO"]),
                Order.status == "FILLED",
            )
            .group_by(Order.condition_id)
        )
        in_rows = (await session.execute(in_stmt)).all()
        in_map = {
            r[0]: {"count": r[1], "notional": float(r[2] or 0.0), "latest": r[3]}
            for r in in_rows
        }

    # -- OUT: exit fills -------------------------------------------------------
    out_map: dict[str, dict] = {}
    if all_condition_ids:
        out_stmt = (
            select(
                Order.condition_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.filled_price * Order.quantity), 0.0),
                func.max(Order.filled_at),
            )
            .where(
                Order.condition_id.in_(all_condition_ids),
                Order.side.in_(["SELL_YES", "SELL_NO"]),
                Order.status == "FILLED",
            )
            .group_by(Order.condition_id)
        )
        out_rows = (await session.execute(out_stmt)).all()
        out_map = {
            r[0]: {"count": r[1], "notional": float(r[2] or 0.0), "latest": r[3]}
            for r in out_rows
        }

    # -- Group Position rows by condition_id -----------------------------------
    by_condition: dict[str, list[Position]] = {}
    for p in pos_rows:
        by_condition.setdefault(p.condition_id, []).append(p)

    # -- Build summaries for condition_ids WITH positions ----------------------
    summaries: dict[str, dict] = {}
    for cid, lots in by_condition.items():
        open_lots = [p for p in lots if p.status == "OPEN"]
        partial_lots = [p for p in lots if p.status == "PARTIAL"]
        closed_lots = [p for p in lots if p.status == "CLOSED"]
        still_open = open_lots + partial_lots

        remaining_qty = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else 0.0)
            for p in still_open
        )
        open_exposure = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else 0.0)
            * (p.entry_price or 0.0)
            for p in still_open
        )
        weighted_avg_entry: Optional[float] = (
            round(open_exposure / remaining_qty, 6) if remaining_qty > 1e-9 else None
        )

        # Card PnL = unrealized PnL of still-open lots ONLY.
        # When all lots are CLOSED, still_open is empty and unrealized_pnl = 0,
        # so the card correctly shows $0.00 (not the realized PnL of closed lots).
        # Realized PnL accumulates at the portfolio level (Resolution Result),
        # not on the per-market card.
        realized_pnl = sum(float(p.realized_pnl or 0.0) for p in lots)
        unrealized_pnl = sum(float(p.unrealized_pnl or 0.0) for p in still_open)

        sides = {p.side for p in still_open}
        if not sides:
            current_side = "NONE"
        elif sides == {"LONG_YES"}:
            current_side = "YES"
        elif sides == {"LONG_NO"}:
            current_side = "NO"
        else:
            current_side = "MIXED"

        in_data = in_map.get(cid, {"count": 0, "notional": 0.0, "latest": None})
        out_data = out_map.get(cid, {"count": 0, "notional": 0.0, "latest": None})

        m = meta.get(cid, {})
        summaries[cid] = {
            "condition_id": cid,
            "asset": m.get("asset"),
            "timeframe": m.get("timeframe"),
            "has_position": True,
            "open_lot_count": len(open_lots),
            "partial_lot_count": len(partial_lots),
            "closed_lot_count": len(closed_lots),
            "total_lot_count": len(lots),
            "active_lot_count": len(open_lots) + len(partial_lots),
            "total_entry_count": in_data["count"],
            "total_entry_notional_usdc": round(in_data["notional"], 6),
            "total_exit_count": out_data["count"],
            "total_exit_notional_usdc": round(out_data["notional"], 6),
            "remaining_quantity": round(remaining_qty, 8),
            "open_exposure_usdc": round(open_exposure, 6),
            "weighted_average_entry_price": weighted_avg_entry,
            "realized_pnl": round(realized_pnl, 6),
            "unrealized_pnl": round(unrealized_pnl, 6),
            # total_pnl = unrealized_pnl of open/partial lots only.
            # Returns 0.0 (not None) when all lots are CLOSED so the card
            # shows "$0.00" instead of "—", signalling a closed position.
            "total_pnl": round(unrealized_pnl, 6),
            "current_side": current_side,
            "latest_entry_at": in_data["latest"],
            "latest_exit_at": out_data["latest"],
        }

    # -- Add zero-rows for active markets with NO positions --------------------
    for cid in active_cids:
        if cid not in summaries:
            m = meta.get(cid, {})
            summaries[cid] = {
                "condition_id": cid,
                "asset": m.get("asset"),
                "timeframe": m.get("timeframe"),
                "has_position": False,
                "open_lot_count": 0,
                "partial_lot_count": 0,
                "closed_lot_count": 0,
                "total_lot_count": 0,
                "active_lot_count": 0,
                "total_entry_count": 0,
                "total_entry_notional_usdc": 0.0,
                "total_exit_count": 0,
                "total_exit_notional_usdc": 0.0,
                "remaining_quantity": 0.0,
                "open_exposure_usdc": 0.0,
                "weighted_average_entry_price": None,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": None,   # null = no position
                "current_side": "NONE",
                "latest_entry_at": None,
                "latest_exit_at": None,
            }

    return summaries
