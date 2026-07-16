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

Sprint 12F+: Now includes live market price fields sourced from the latest
MarketPriceSnapshot, side-split exposure (up_open_exposure / down_open_exposure),
freshly-computed unrealized PnL from executable bid prices, and freshness flag.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.order import Order
from app.models.position import Position
from app.repositories.position_repository import OPEN_LIKE_STATUSES

# Stale threshold: 2× the normal refresh interval (same logic as /price endpoint)
_STALE_THRESHOLD_SECONDS = settings.PRICE_REFRESH_SECONDS * 2


def _compute_stale(captured_at: Optional[datetime]) -> bool:
    """Return True if the snapshot is older than the stale threshold (or absent)."""
    if captured_at is None:
        return True
    cap = captured_at
    if cap.tzinfo is None:
        cap = cap.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - cap).total_seconds()
    return age > _STALE_THRESHOLD_SECONDS


def _derive_down_fields(
    snap: "MarketPriceSnapshot",
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Derive DOWN (NO token) bid/ask/mark from a snapshot.

    Primary source: snap.no_bid / snap.no_ask / snap.no_mid (stored directly).
    Fallback (when NO fields are absent): complement of YES bid/ask.
        down_bid = 1 - yes_ask
        down_ask = 1 - yes_bid
        down_mark = (down_bid + down_ask) / 2
    """
    down_bid = snap.no_bid
    down_ask = snap.no_ask
    down_mark = snap.no_mid

    if down_bid is None and snap.yes_ask is not None:
        down_bid = round(1.0 - snap.yes_ask, 6)
    if down_ask is None and snap.yes_bid is not None:
        down_ask = round(1.0 - snap.yes_bid, 6)
    if down_mark is None:
        if down_bid is not None and down_ask is not None:
            down_mark = round((down_bid + down_ask) / 2.0, 6)
        elif snap.yes_mid is not None:
            down_mark = round(1.0 - snap.yes_mid, 6)

    return down_bid, down_ask, down_mark


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

    Fields follow the spec §10 contract:
      condition_id, asset, timeframe,
      market_updated_at, market_data_stale,
      up_bid, up_ask, up_mark,
      down_bid, down_ask, down_mark,
      up_open_exposure, down_open_exposure, active_side,
      entry_fill_count, entry_notional,
      exit_fill_count, exit_proceeds,
      open_lot_count, open_shares, average_entry,
      realized_pnl, unrealized_pnl, total_pnl,
      (+ legacy aliases kept for backward compat)
    """
    active_cids: list[str] = []
    meta: dict[str, dict] = {}   # condition_id → {asset, timeframe}
    if active_markets:
        for m in active_markets:
            cid = m["condition_id"]
            active_cids.append(cid)
            meta[cid] = {"asset": m.get("asset"), "timeframe": m.get("timeframe")}

    # ── Query positions (lots) ─────────────────────────────────────────────────
    pos_stmt = select(Position)
    if active_cids:
        pos_stmt = pos_stmt.where(Position.condition_id.in_(active_cids))
    pos_rows = list((await session.execute(pos_stmt)).scalars().all())

    # condition_ids that actually have positions
    all_condition_ids = list({p.condition_id for p in pos_rows})

    # ── IN: entry fills ────────────────────────────────────────────────────────
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

    # ── OUT: exit fills ────────────────────────────────────────────────────────
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

    # ── Latest price snapshot per active condition_id ─────────────────────────
    # Query all active condition_ids (not just those with positions) so zero-rows
    # also get price data.
    snap_cids = list(set(active_cids) | set(all_condition_ids))
    snap_map: dict[str, "MarketPriceSnapshot"] = {}
    if snap_cids:
        snap_subq = (
            select(
                MarketPriceSnapshot.condition_id.label("cid"),
                func.max(MarketPriceSnapshot.captured_at).label("max_cap"),
            )
            .where(MarketPriceSnapshot.condition_id.in_(snap_cids))
            .group_by(MarketPriceSnapshot.condition_id)
            .subquery()
        )
        snap_stmt = select(MarketPriceSnapshot).join(
            snap_subq,
            (MarketPriceSnapshot.condition_id == snap_subq.c.cid)
            & (MarketPriceSnapshot.captured_at == snap_subq.c.max_cap),
        )
        snap_rows_q = list((await session.execute(snap_stmt)).scalars().all())
        snap_map = {s.condition_id: s for s in snap_rows_q}

    # ── Group Position rows by condition_id ───────────────────────────────────
    by_condition: dict[str, list[Position]] = {}
    for p in pos_rows:
        by_condition.setdefault(p.condition_id, []).append(p)

    # ── Build summaries for condition_ids WITH positions ──────────────────────
    summaries: dict[str, dict] = {}
    for cid, lots in by_condition.items():
        open_lots    = [p for p in lots if p.status == "OPEN"]
        partial_lots = [p for p in lots if p.status == "PARTIAL"]
        closed_lots  = [p for p in lots if p.status == "CLOSED"]
        still_open   = open_lots + partial_lots

        # ── Exposure split by side ─────────────────────────────────────────────
        # up_open_exposure  → LONG_YES (YES token / "UP" outcome)
        # down_open_exposure → LONG_NO  (NO  token / "DOWN" outcome)
        up_lots   = [p for p in still_open if p.side in ("LONG_YES",)]
        down_lots = [p for p in still_open if p.side in ("LONG_NO",)]

        up_open_exposure = sum(
            (p.remaining_quantity or 0.0) * (p.entry_price or 0.0)
            for p in up_lots
        )
        down_open_exposure = sum(
            (p.remaining_quantity or 0.0) * (p.entry_price or 0.0)
            for p in down_lots
        )
        open_exposure = up_open_exposure + down_open_exposure

        remaining_qty = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else 0.0)
            for p in still_open
        )
        weighted_avg_entry: Optional[float] = (
            round(open_exposure / remaining_qty, 6) if remaining_qty > 1e-9 else None
        )

        sides = {p.side for p in still_open}
        if not sides:
            current_side = "NONE"
        elif sides == {"LONG_YES"}:
            current_side = "YES"
        elif sides == {"LONG_NO"}:
            current_side = "NO"
        else:
            current_side = "MIXED"

        # active_side is the same semantics as current_side (alias per spec §10)
        active_side = current_side

        # ── Price fields from latest snapshot ─────────────────────────────────
        snap = snap_map.get(cid)
        if snap is not None:
            up_bid  = snap.yes_bid
            up_ask  = snap.yes_ask
            up_mark = snap.yes_mid
            down_bid, down_ask, down_mark = _derive_down_fields(snap)
            market_updated_at = snap.captured_at
            market_data_stale = _compute_stale(snap.captured_at)
        else:
            up_bid = up_ask = up_mark = None
            down_bid = down_ask = down_mark = None
            market_updated_at = None
            market_data_stale = True

        # ── Unrealized PnL — computed fresh from executable bid prices ─────────
        # Uses the live YES/NO bid (executable price) rather than stored value.
        # Fallback to stored p.unrealized_pnl when snapshot is absent.
        realized_pnl = sum(float(p.realized_pnl or 0.0) for p in lots)
        if snap is not None:
            yes_bid_val = snap.yes_bid
            _db, _da, _dm = _derive_down_fields(snap)
            no_bid_val = _db  # DOWN executable bid = complemented or stored no_bid

            fresh_unrealized = 0.0
            for p in still_open:
                qty   = p.remaining_quantity or 0.0
                entry = p.entry_price or 0.0
                if qty <= 0:
                    continue
                if p.side == "LONG_YES" and yes_bid_val is not None:
                    fresh_unrealized += qty * (yes_bid_val - entry)
                elif p.side == "LONG_NO" and no_bid_val is not None:
                    fresh_unrealized += qty * (no_bid_val - entry)
                else:
                    # No bid price available — fall back to stored value
                    fresh_unrealized += float(p.unrealized_pnl or 0.0)
            unrealized_pnl = round(fresh_unrealized, 6)
        else:
            # No snapshot: use stored unrealized_pnl
            unrealized_pnl = sum(float(p.unrealized_pnl or 0.0) for p in still_open)

        in_data  = in_map.get(cid, {"count": 0, "notional": 0.0, "latest": None})
        out_data = out_map.get(cid, {"count": 0, "notional": 0.0, "latest": None})

        m_meta = meta.get(cid, {})
        summaries[cid] = {
            # ── Identity ────────────────────────────────────────────────────────
            "condition_id": cid,
            "asset":       m_meta.get("asset"),
            "timeframe":   m_meta.get("timeframe"),

            # ── Market price (spec §10) ─────────────────────────────────────────
            "market_updated_at": market_updated_at,
            "market_data_stale": market_data_stale,
            "up_bid":   up_bid,
            "up_ask":   up_ask,
            "up_mark":  up_mark,
            "down_bid": down_bid,
            "down_ask": down_ask,
            "down_mark": down_mark,

            # ── Position state ──────────────────────────────────────────────────
            "has_position":    True,
            "open_lot_count":  len(open_lots),
            "partial_lot_count": len(partial_lots),
            "closed_lot_count":  len(closed_lots),
            "total_lot_count":   len(lots),
            "active_lot_count":  len(open_lots) + len(partial_lots),

            # ── Side exposure (spec §10) ─────────────────────────────────────────
            "up_open_exposure":   round(up_open_exposure, 6),
            "down_open_exposure": round(down_open_exposure, 6),
            "open_exposure_usdc": round(open_exposure, 6),  # legacy combined
            "active_side":        active_side,
            "current_side":       current_side,  # legacy alias

            # ── IN — entry fills (spec §10 names + legacy names) ────────────────
            "entry_fill_count":          in_data["count"],
            "entry_notional":            round(in_data["notional"], 6),
            "total_entry_count":         in_data["count"],        # legacy
            "total_entry_notional_usdc": round(in_data["notional"], 6),  # legacy

            # ── OUT — exit fills (spec §10 names + legacy names) ────────────────
            "exit_fill_count":           out_data["count"],
            "exit_proceeds":             round(out_data["notional"], 6),
            "total_exit_count":          out_data["count"],        # legacy
            "total_exit_notional_usdc":  round(out_data["notional"], 6),  # legacy

            # ── Quantity / price summary (spec §10 names + legacy names) ─────────
            "open_shares":                    round(remaining_qty, 8),
            "remaining_quantity":             round(remaining_qty, 8),  # legacy
            "average_entry":                  weighted_avg_entry,
            "weighted_average_entry_price":   weighted_avg_entry,  # legacy

            # ── PnL ─────────────────────────────────────────────────────────────
            "realized_pnl":   round(realized_pnl, 6),
            "unrealized_pnl": round(unrealized_pnl, 6),
            "total_pnl":      round(unrealized_pnl, 6),

            # ── Timestamps ──────────────────────────────────────────────────────
            "latest_entry_at": in_data["latest"],
            "latest_exit_at":  out_data["latest"],
        }

    # ── Add zero-rows for active markets with NO positions ────────────────────
    for cid in active_cids:
        if cid not in summaries:
            m_meta = meta.get(cid, {})
            snap = snap_map.get(cid)
            if snap is not None:
                up_bid  = snap.yes_bid
                up_ask  = snap.yes_ask
                up_mark = snap.yes_mid
                down_bid, down_ask, down_mark = _derive_down_fields(snap)
                market_updated_at = snap.captured_at
                market_data_stale = _compute_stale(snap.captured_at)
            else:
                up_bid = up_ask = up_mark = None
                down_bid = down_ask = down_mark = None
                market_updated_at = None
                market_data_stale = True

            summaries[cid] = {
                "condition_id": cid,
                "asset":        m_meta.get("asset"),
                "timeframe":    m_meta.get("timeframe"),

                "market_updated_at": market_updated_at,
                "market_data_stale": market_data_stale,
                "up_bid":    up_bid,
                "up_ask":    up_ask,
                "up_mark":   up_mark,
                "down_bid":  down_bid,
                "down_ask":  down_ask,
                "down_mark": down_mark,

                "has_position":       False,
                "open_lot_count":     0,
                "partial_lot_count":  0,
                "closed_lot_count":   0,
                "total_lot_count":    0,
                "active_lot_count":   0,

                "up_open_exposure":   0.0,
                "down_open_exposure": 0.0,
                "open_exposure_usdc": 0.0,
                "active_side":        "NONE",
                "current_side":       "NONE",

                "entry_fill_count":          0,
                "entry_notional":            0.0,
                "total_entry_count":         0,
                "total_entry_notional_usdc": 0.0,

                "exit_fill_count":           0,
                "exit_proceeds":             0.0,
                "total_exit_count":          0,
                "total_exit_notional_usdc":  0.0,

                "open_shares":                  0.0,
                "remaining_quantity":           0.0,
                "average_entry":                None,
                "weighted_average_entry_price": None,

                "realized_pnl":   0.0,
                "unrealized_pnl": 0.0,
                "total_pnl":      None,  # null = no position

                "latest_entry_at": None,
                "latest_exit_at":  None,
            }

    return summaries
