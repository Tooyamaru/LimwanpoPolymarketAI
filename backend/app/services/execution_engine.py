"""
Execution Engine — Layer 7 (Paper Mode).

Reads RISK_APPROVED TradeDecision rows and executes them.

Entry path (OPEN_LONG_YES / OPEN_LONG_NO):
  Simulates an immediate market fill, persists an Order record, then marks
  the TradeDecision as EXECUTED.

  Paper-mode fill logic (no slippage, instant fill):
    OPEN_LONG_YES → side=LONG_YES, fill_price = yes_ask
    OPEN_LONG_NO  → side=LONG_NO,  fill_price = 1.0 - yes_bid

Exit path (CLOSE_POSITION):
  Loads the target position, computes the executable exit price using live
  opportunity data (bid-side only, never mid), calls
  position_service.close_position(), and marks the TradeDecision EXECUTED.

  Exit price:
    LONG_YES → yes_bid
    LONG_NO  → 1 - yes_ask

If required price data is missing the decision is skipped (not failed) and
retried on the next cycle.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.repositories import order_repository as order_repo

logger = get_logger(__name__)


class ExecutionEngine:
    """
    Simulates order execution for actionable TradeDecision rows.

    Usage (from FastAPI lifespan or background loop)::

        engine = ExecutionEngine()
        result = await engine.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        """
        Execute one full paper-mode cycle.

        Entry path: processes RISK_APPROVED OPEN_LONG_YES / OPEN_LONG_NO decisions.
        Exit path:  processes RISK_APPROVED CLOSE_POSITION decisions.

        Returns
        -------
        dict with cycle summary statistics.
        """
        started = datetime.now(timezone.utc)

        # ── Entry path: RISK_APPROVED OPEN_LONG decisions ──────────────────────
        entry_result = await session.execute(
            select(TradeDecision)
            .where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "RISK_APPROVED",
            )
            .order_by(TradeDecision.decided_at)
        )
        pending: list[TradeDecision] = list(entry_result.scalars().all())

        filled = 0
        skipped = 0
        errors = 0

        for td in pending:
            try:
                _, did_skip = await self._execute_decision(session, td)
                if did_skip:
                    skipped += 1
                else:
                    filled += 1
            except Exception as exc:
                logger.error(
                    "Execution engine error (entry path)",
                    decision_id=td.id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    error=str(exc),
                )
                errors += 1

        # ── Exit path: RISK_APPROVED CLOSE_POSITION decisions ──────────────────
        exit_result = await session.execute(
            select(TradeDecision)
            .where(
                TradeDecision.decision == "CLOSE_POSITION",
                TradeDecision.status == "RISK_APPROVED",
            )
            .order_by(TradeDecision.decided_at)
        )
        pending_exits: list[TradeDecision] = list(exit_result.scalars().all())

        exits_closed = 0
        exits_skipped = 0

        for td in pending_exits:
            try:
                did_skip = await self._execute_close_decision(session, td)
                if did_skip:
                    exits_skipped += 1
                else:
                    exits_closed += 1
            except Exception as exc:
                logger.error(
                    "Execution engine error (exit path)",
                    decision_id=td.id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        if not pending and not pending_exits:
            logger.debug("Execution engine: no decisions to process")
        else:
            logger.info(
                "Execution engine cycle complete",
                decisions_processed=len(pending),
                orders_filled=filled,
                orders_skipped=skipped,
                exits_closed=exits_closed,
                exits_skipped=exits_skipped,
                errors=errors,
                duration_ms=elapsed_ms,
            )

        return {
            "decisions_processed": len(pending),
            "orders_filled": filled,
            "orders_skipped": skipped,
            "exits_closed": exits_closed,
            "exits_skipped": exits_skipped,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _execute_close_decision(
        self,
        session: AsyncSession,
        td: TradeDecision,
    ) -> bool:
        """
        Execute one CLOSE_POSITION TradeDecision.

        Returns True (skipped) when the position is missing, already closed,
        or the executable exit price is unavailable.  Returns False on success.
        """
        from app.services.position_service import PositionService

        if td.target_position_id is None:
            logger.warning(
                "Close decision has no target_position_id, skipping",
                decision_id=td.id,
            )
            await session.execute(
                update(TradeDecision)
                .where(TradeDecision.id == td.id)
                .values(status="EXECUTED")
            )
            return True

        # ── Load target position ───────────────────────────────────────────────
        pos_result = await session.execute(
            select(Position).where(Position.id == td.target_position_id)
        )
        pos = pos_result.scalar_one_or_none()

        if pos is None:
            logger.warning(
                "Close decision target position not found, skipping",
                decision_id=td.id,
                target_position_id=td.target_position_id,
            )
            await session.execute(
                update(TradeDecision)
                .where(TradeDecision.id == td.id)
                .values(status="EXECUTED")
            )
            return True

        if pos.status != "OPEN":
            logger.info(
                "Close decision target position already closed, marking EXECUTED",
                decision_id=td.id,
                position_id=pos.id,
                position_status=pos.status,
            )
            await session.execute(
                update(TradeDecision)
                .where(TradeDecision.id == td.id)
                .values(status="EXECUTED")
            )
            return True

        # ── Load fresh opportunity data for executable exit price ──────────────
        opp_result = await session.execute(
            select(Opportunity).where(Opportunity.condition_id == pos.condition_id)
        )
        opp = opp_result.scalar_one_or_none()

        if pos.side == "LONG_YES":
            if opp is None or opp.yes_bid is None:
                logger.warning(
                    "Close decision: yes_bid unavailable, retrying next cycle",
                    decision_id=td.id,
                    position_id=pos.id,
                    side=pos.side,
                )
                return True
            exit_price = round(opp.yes_bid, 6)
        else:  # LONG_NO
            if opp is None or opp.yes_ask is None:
                logger.warning(
                    "Close decision: yes_ask unavailable, retrying next cycle",
                    decision_id=td.id,
                    position_id=pos.id,
                    side=pos.side,
                )
                return True
            exit_price = round(1.0 - opp.yes_ask, 6)

        # ── Create exit order record (SELL_YES / SELL_NO) ─────────────────────
        now = datetime.now(timezone.utc)
        exit_side = "SELL_YES" if pos.side == "LONG_YES" else "SELL_NO"
        close_order = await order_repo.create_order(
            session,
            decision_id=td.id,
            condition_id=pos.condition_id,
            asset=pos.asset,
            timeframe=pos.timeframe,
            side=exit_side,
            order_type="MARKET",
            quantity=pos.quantity,
            requested_price=exit_price,
            filled_price=exit_price,
            status="FILLED",
            created_at=now,
            filled_at=now,
        )
        # Flush to obtain close_order.id before linking it to the position
        await session.flush()

        # ── Close the position with full audit trail ───────────────────────────
        pos_svc = PositionService()
        await pos_svc.close_position(
            session,
            pos.id,
            closing_price=exit_price,
            close_reason=td.exit_reason,
            close_decision_id=td.id,
            close_order_id=close_order.id,
        )

        # ── Mark trade decision as EXECUTED ────────────────────────────────────
        await session.execute(
            update(TradeDecision)
            .where(TradeDecision.id == td.id)
            .values(status="EXECUTED")
        )

        logger.info(
            "Position closed via exit decision",
            decision_id=td.id,
            position_id=pos.id,
            close_order_id=close_order.id,
            asset=pos.asset,
            timeframe=pos.timeframe,
            side=pos.side,
            exit_side=exit_side,
            exit_price=exit_price,
            entry_price=pos.entry_price,
            exit_reason=td.exit_reason,
        )
        return False

    async def _execute_decision(
        self,
        session: AsyncSession,
        td: TradeDecision,
    ) -> tuple[Optional[object], bool]:
        """
        Process one TradeDecision.

        Returns (order_or_None, skipped_flag).
        skipped_flag is True when price data is unavailable.
        """
        now = datetime.now(timezone.utc)

        # ── Determine side and fill price ──────────────────────────────────────
        if td.decision == "OPEN_LONG_YES":
            side = "LONG_YES"
            # Buy YES tokens at the ask
            if td.yes_ask is None:
                logger.warning(
                    "Execution skipped: yes_ask missing",
                    decision_id=td.id,
                    asset=td.asset,
                )
                return None, True
            requested_price = round(td.yes_ask, 4)

        else:  # OPEN_LONG_NO
            side = "LONG_NO"
            # Buy NO tokens at implied ask = 1 - yes_bid
            if td.yes_bid is None:
                logger.warning(
                    "Execution skipped: yes_bid missing",
                    decision_id=td.id,
                    asset=td.asset,
                )
                return None, True
            requested_price = round(1.0 - td.yes_bid, 4)

        fill_price = requested_price  # paper mode: no slippage

        # ── Compute quantity from position_size_usdc (Layer 13) ───────────────
        if td.position_size_usdc is not None and fill_price > 0:
            quantity = round(td.position_size_usdc / fill_price, 6)
        else:
            # Backward-compat fallback for decisions without sizing (legacy rows)
            quantity = 1.0

        # ── Create order record ────────────────────────────────────────────────
        order = await order_repo.create_order(
            session,
            decision_id=td.id,
            condition_id=td.condition_id,
            asset=td.asset,
            timeframe=td.timeframe,
            side=side,
            order_type="MARKET",
            quantity=quantity,
            requested_price=requested_price,
            filled_price=fill_price,
            status="FILLED",
            created_at=now,
            filled_at=now,
        )

        # ── Mark trade_decision as EXECUTED ───────────────────────────────────
        await session.execute(
            update(TradeDecision)
            .where(TradeDecision.id == td.id)
            .values(status="EXECUTED")
        )

        logger.info(
            "Order filled (paper)",
            decision_id=td.id,
            asset=td.asset,
            timeframe=td.timeframe,
            side=side,
            fill_price=fill_price,
            position_size_usdc=td.position_size_usdc,
            quantity=quantity,
        )

        return order, False
