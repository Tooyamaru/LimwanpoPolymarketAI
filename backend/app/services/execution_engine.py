"""
Execution Engine — Layer 7 (Paper Mode).

Reads PENDING OPEN_LONG_YES / OPEN_LONG_NO TradeDecision rows, simulates
an immediate market fill, persists an Order record, then marks the
TradeDecision as EXECUTED.

Paper-mode fill logic (no slippage, instant fill):
  OPEN_LONG_YES → side=LONG_YES, fill_price = yes_ask
  OPEN_LONG_NO  → side=LONG_NO,  fill_price = 1.0 - yes_bid

Both yes_ask and yes_bid come directly from the TradeDecision row, which
was populated by the Opportunity Engine from the latest CLOB snapshot.
If price data is missing the order is skipped (not failed) and retried
on the next cycle.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.trade_decision import TradeDecision
from app.services import order_repository as order_repo

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

        Returns
        -------
        dict with cycle summary statistics.
        """
        started = datetime.now(timezone.utc)

        # ── Fetch PENDING actionable decisions ─────────────────────────────────
        result = await session.execute(
            select(TradeDecision)
            .where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "PENDING",
            )
            .order_by(TradeDecision.decided_at)
        )
        pending: list[TradeDecision] = list(result.scalars().all())

        if not pending:
            logger.debug("Execution engine: no pending decisions to process")
            return {
                "decisions_processed": 0,
                "orders_filled": 0,
                "orders_skipped": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        filled = 0
        skipped = 0
        errors = 0

        for td in pending:
            try:
                order, did_skip = await self._execute_decision(session, td)
                if did_skip:
                    skipped += 1
                else:
                    filled += 1
            except Exception as exc:
                logger.error(
                    "Execution engine error",
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

        logger.info(
            "Execution engine cycle complete",
            decisions_processed=len(pending),
            orders_filled=filled,
            orders_skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )

        return {
            "decisions_processed": len(pending),
            "orders_filled": filled,
            "orders_skipped": skipped,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

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

        # ── Create order record ────────────────────────────────────────────────
        order = await order_repo.create_order(
            session,
            decision_id=td.id,
            condition_id=td.condition_id,
            asset=td.asset,
            timeframe=td.timeframe,
            side=side,
            order_type="MARKET",
            quantity=1.0,
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
        )

        return order, False
