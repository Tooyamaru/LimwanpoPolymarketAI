"""
TradeReplayService — Phase 5: Trade Replay.

Reconstructs the full decision timeline for a single closed position,
producing a step-by-step audit trail of what happened.

Also provides a dataset export endpoint that flattens all closed trades
into rows suitable for ML/statistical analysis.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.order import Order
from app.models.position import Position
from app.models.signal import Signal
from app.models.trade_decision import TradeDecision
from app.models.trade_evaluation import TradeEvaluation
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)


class TradeReplayService:
    """
    Replays closed positions as step-by-step event timelines.

    Usage::

        svc = TradeReplayService()
        replay = await svc.replay_position(position_id, session)
        dataset = await svc.get_dataset(session)
    """

    async def replay_position(
        self, position_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """
        Reconstruct the full event timeline for a single closed position.
        Returns None if the position does not exist or is not CLOSED.
        """
        pos_res = await session.execute(
            select(Position).where(
                Position.id == position_id,
                Position.status == "CLOSED",
            )
        )
        pos: Optional[Position] = pos_res.scalar_one_or_none()
        if pos is None:
            return None

        timeline: list[dict] = []
        step = 0

        # ── Step 0: position opened ───────────────────────────────────────────
        step += 1
        timeline.append({
            "step": step,
            "event": "POSITION_OPENED",
            "timestamp": pos.opened_at,
            "value": pos.entry_price,
            "note": (
                f"Entered {pos.side} at {pos.entry_price:.4f} "
                f"qty={pos.quantity:.2f} on {pos.asset}/{pos.timeframe}"
            ),
        })

        # ── Step 1: find the entry order ─────────────────────────────────────
        if pos.order_id:
            order_res = await session.execute(
                select(Order).where(Order.id == pos.order_id)
            )
            entry_order: Optional[Order] = order_res.scalar_one_or_none()
            if entry_order is not None:
                step += 1
                fee = float(getattr(entry_order, "entry_fee_usdc", None) or 0.0)
                timeline.append({
                    "step": step,
                    "event": "ENTRY_ORDER_FILLED",
                    "timestamp": entry_order.filled_at if hasattr(entry_order, "filled_at") else pos.opened_at,
                    "value": float(entry_order.filled_price or pos.entry_price),
                    "note": (
                        f"Entry order filled at {entry_order.filled_price or pos.entry_price:.4f} "
                        f"fee={fee:.4f} USDC"
                    ),
                })

        # ── Step 2: find strategy decision that opened this position ──────────
        decision_res = await session.execute(
            select(TradeDecision).where(
                TradeDecision.condition_id == pos.condition_id,
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "EXECUTED",
            ).order_by(TradeDecision.decided_at.asc()).limit(1)
        )
        open_decision: Optional[TradeDecision] = decision_res.scalar_one_or_none()
        if open_decision is not None:
            step += 1
            timeline.append({
                "step": step,
                "event": "STRATEGY_DECISION",
                "timestamp": open_decision.decided_at,
                "value": open_decision.opportunity_score,
                "note": (
                    f"{open_decision.decision} — opp_score={open_decision.opportunity_score:.1f} "
                    f"mid={open_decision.yes_mid}"
                ),
            })

        # ── Step 3: peak PnL marker ───────────────────────────────────────────
        if pos.peak_pnl_usdc is not None:
            step += 1
            timeline.append({
                "step": step,
                "event": "PEAK_PNL_REACHED",
                "timestamp": None,  # not timestamped — computed at tracking time
                "value": float(pos.peak_pnl_usdc),
                "note": f"Highest unrealized PnL recorded: {pos.peak_pnl_usdc:.4f} USDC",
            })

        # ── Step 4: close decision ────────────────────────────────────────────
        if pos.close_decision_id:
            close_dec_res = await session.execute(
                select(TradeDecision).where(TradeDecision.id == pos.close_decision_id)
            )
            close_decision: Optional[TradeDecision] = close_dec_res.scalar_one_or_none()
            if close_decision is not None:
                step += 1
                timeline.append({
                    "step": step,
                    "event": "CLOSE_DECISION",
                    "timestamp": close_decision.decided_at,
                    "value": None,
                    "note": (
                        f"CLOSE_POSITION triggered — reason={close_decision.exit_reason}"
                    ),
                })

        # ── Step 5: position closed ───────────────────────────────────────────
        step += 1
        timeline.append({
            "step": step,
            "event": "POSITION_CLOSED",
            "timestamp": pos.closed_at,
            "value": pos.exit_price,
            "note": (
                f"Closed at {pos.exit_price:.4f} reason={pos.close_reason} "
                f"realized_pnl={pos.realized_pnl:+.4f} USDC"
                if pos.exit_price is not None and pos.realized_pnl is not None
                else "Position closed"
            ),
        })

        # ── Fetch evaluation if it exists ─────────────────────────────────────
        eval_res = await session.execute(
            select(TradeEvaluation).where(TradeEvaluation.position_id == position_id)
        )
        evaluation = eval_res.scalar_one_or_none()

        # ── Hold time ─────────────────────────────────────────────────────────
        hold_min: Optional[float] = None
        if pos.opened_at is not None and pos.closed_at is not None:
            opened = pos.opened_at
            closed = pos.closed_at
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            if closed.tzinfo is None:
                closed = closed.replace(tzinfo=timezone.utc)
            hold_min = round((closed - opened).total_seconds() / 60.0, 4)

        return {
            "position_id": pos.id,
            "asset": pos.asset,
            "timeframe": pos.timeframe,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": pos.exit_price,
            "realized_pnl": pos.realized_pnl,
            "close_reason": pos.close_reason,
            "hold_minutes": hold_min,
            "evaluation": evaluation,
            "timeline": timeline,
        }

    async def get_dataset(
        self, session: AsyncSession, limit: int = 1000, offset: int = 0
    ) -> dict:
        """
        Export closed trades as a flat dataset for analysis / ML.
        Uses DB-level pagination and a LEFT JOIN to pull evaluation data
        without loading the full table into Python.
        """
        from sqlalchemy import func as sqlfunc

        # Total count — single COUNT query
        total_res = await session.execute(
            select(func.count(Position.id)).where(Position.status == "CLOSED")
        )
        total: int = total_res.scalar_one() or 0

        # Paginated positions via DB LIMIT/OFFSET
        pos_res = await session.execute(
            select(Position)
            .where(Position.status == "CLOSED")
            .order_by(Position.closed_at.asc())
            .limit(limit)
            .offset(offset)
        )
        positions: list[Position] = list(pos_res.scalars().all())

        if not positions:
            return {"total_rows": total, "rows": []}

        # Fetch evaluations only for this page's position IDs
        pos_ids = [p.id for p in positions]
        eval_res = await session.execute(
            select(TradeEvaluation).where(TradeEvaluation.position_id.in_(pos_ids))
        )
        evals: dict[int, TradeEvaluation] = {
            ev.position_id: ev for ev in eval_res.scalars().all()
        }

        rows = []
        for pos in positions:
            ev = evals.get(pos.id)
            hold_min: Optional[float] = None
            if pos.opened_at is not None and pos.closed_at is not None:
                opened = pos.opened_at
                closed = pos.closed_at
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                if closed.tzinfo is None:
                    closed = closed.replace(tzinfo=timezone.utc)
                hold_min = round((closed - opened).total_seconds() / 60.0, 4)

            rows.append({
                "position_id": pos.id,
                "asset": pos.asset,
                "timeframe": pos.timeframe,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "exit_price": pos.exit_price,
                "realized_pnl": pos.realized_pnl,
                "total_fee_usdc": getattr(pos, "total_fee_usdc", None),
                "close_reason": pos.close_reason,
                "hold_minutes": hold_min,
                "opportunity_score_at_entry": ev.opportunity_score_at_entry if ev else None,
                "signal_confidence_at_entry": ev.signal_confidence_at_entry if ev else None,
                "quality_score": ev.quality_score if ev else None,
                "grade": ev.grade if ev else None,
                "opened_at": pos.opened_at,
                "closed_at": pos.closed_at,
            })

        return {"total_rows": total, "rows": rows}
