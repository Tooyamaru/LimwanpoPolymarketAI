"""
Execution Engine — Layer 7 (Paper Mode).

Reads RISK_APPROVED TradeDecision rows and executes them.

Entry path (OPEN_LONG_YES / OPEN_LONG_NO):
  Simulates an immediate market fill, persists an Order record, then marks
  the TradeDecision as EXECUTED.

  Paper-mode fill logic (no slippage, instant fill):
    OPEN_LONG_YES → side=LONG_YES, fill_price = yes_ask
    OPEN_LONG_NO  → side=LONG_NO,  fill_price = 1.0 - yes_bid

  Fee simulation (Phase 4 Part D):
    entry_fee_usdc = fill_price × quantity × POLYMARKET_FEE_RATE
    Stored on the Order row.  The Position Service reads this when opening the
    position and sets position.total_fee_usdc = entry_fee_usdc.

Exit path (CLOSE_POSITION):
  Loads the target position, computes the executable exit price using live
  opportunity data (bid-side only, never mid), calls
  position_service.close_position(), and marks the TradeDecision EXECUTED.

  Exit price:
    LONG_YES → yes_bid
    LONG_NO  → 1 - yes_ask

  Exit fee:
    exit_fee_usdc = exit_price × quantity × POLYMARKET_FEE_RATE
    Passed to close_position() which deducts total fees from realized_pnl.

If required price data is missing the decision is skipped (not failed) and
retried on the next cycle.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.repositories import order_repository as order_repo
from app.utils.prediction_window import PRED_WINDOW_LIVE, get_prediction_window_lifecycle

logger = get_logger(__name__)


async def _reject_window(
    session: AsyncSession,
    td: TradeDecision,
    reason: str,
    now_iso: str,
) -> tuple:
    """
    Mark an entry decision BLOCKED (terminal) when prediction-window
    validation fails, then return the (None, True) skip sentinel.

    Marking BLOCKED releases the capital slot — the Risk Engine and
    Execution Engine will never retry a BLOCKED decision.
    """
    await session.execute(
        update(TradeDecision)
        .where(TradeDecision.id == td.id)
        .values(status="BLOCKED")
    )
    logger.warning(
        "Execution rejected: stale prediction window",
        decision_id=td.id,
        condition_id=td.condition_id,
        asset=td.asset,
        timeframe=td.timeframe,
        reject_reason=reason,
        now_utc=now_iso,
    )
    return None, True


def _compute_fee(price: float, quantity: float) -> float:
    """
    Compute the Polymarket trading fee for one side of a transaction.

    fee = price × quantity × POLYMARKET_FEE_RATE

    Returns 0.0 in paper mode (POLYMARKET_FEE_RATE = 0.0 by default).
    """
    return round(price * quantity * settings.POLYMARKET_FEE_RATE, 6)


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

        if pos.status not in ("OPEN", "PARTIAL"):
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

        # ── Phase 10: forced-expiry exit price takes absolute priority ─────────
        # ExitEngine computes this from direct Polymarket resolution data
        # (OutcomeLearning.final_yes_price / final_no_price) when a market has
        # already expired. Live Opportunity bid/ask data is stale/meaningless
        # for an expired market, so it must NEVER override this value.
        if td.forced_exit_price is not None:
            exit_price = round(td.forced_exit_price, 6)
            logger.info(
                "Close decision: using forced resolution-based exit price",
                decision_id=td.id,
                position_id=pos.id,
                side=pos.side,
                forced_exit_price=exit_price,
            )
        else:
            # ── Load fresh opportunity data for executable exit price ──────────
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

        # Close the lot's remaining quantity — for a lot that already had a
        # prior partial exit this is less than the original entry quantity.
        close_qty = pos.remaining_quantity if pos.remaining_quantity is not None else pos.quantity

        # ── Compute exit fee (Phase 4 Part D) ─────────────────────────────────
        exit_fee_usdc = _compute_fee(exit_price, close_qty)

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
            quantity=close_qty,
            requested_price=exit_price,
            filled_price=exit_price,
            status="FILLED",
            created_at=now,
            filled_at=now,
            exit_fee_usdc=exit_fee_usdc,
        )
        # Flush to obtain close_order.id before linking it to the position
        await session.flush()

        # ── Close the position with full audit trail ───────────────────────────
        # ExitEngine triggers here always target the entire remaining balance
        # of this lot (no ExitEngine trigger currently requests a partial
        # exit) — pass close_quantity explicitly so this stays correct even
        # if the lot already had a prior partial close.
        pos_svc = PositionService()
        await pos_svc.close_position(
            session,
            pos.id,
            closing_price=exit_price,
            close_reason=td.exit_reason,
            close_decision_id=td.id,
            close_order_id=close_order.id,
            exit_fee_usdc=exit_fee_usdc,
            close_quantity=close_qty,
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
            exit_fee_usdc=exit_fee_usdc,
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
        _now_iso = now.isoformat()

        # ── Fetch current MarketUniverse by exact decision condition_id ───────
        # One decision must never be redirected to a different market.
        _market_row = (await session.execute(
            select(MarketUniverse).where(MarketUniverse.condition_id == td.condition_id)
        )).scalar_one_or_none()

        if _market_row is None:
            return await _reject_window(session, td, "MARKET_NOT_IN_UNIVERSE", _now_iso)

        # ── Prediction-window binding validation (ENTRY-ONLY) ─────────────────
        # All 11 checks must pass before any price fetch or order submission.

        # 1. Decision binding fields must be fully populated.
        if (
            not td.decision_event_slug
            or td.decision_prediction_window_start is None
            or td.decision_prediction_window_end is None
        ):
            return await _reject_window(session, td, "INVALID_DECISION_WINDOW_BINDING", _now_iso)

        # 2. Condition identity must match the current market row.
        if td.condition_id != _market_row.condition_id:
            return await _reject_window(session, td, "DECISION_CONDITION_STALE", _now_iso)

        # 3. Event slug must match the current market (detects 5-minute rollover).
        if td.decision_event_slug != _market_row.event_slug:
            return await _reject_window(session, td, "DECISION_EVENT_SLUG_STALE", _now_iso)

        # 4. Window start must match (decision was made for a different slot).
        if td.decision_prediction_window_start != _market_row.prediction_window_start:
            return await _reject_window(session, td, "DECISION_WINDOW_STALE", _now_iso)

        # 5. Window end must match.
        if td.decision_prediction_window_end != _market_row.prediction_window_end:
            return await _reject_window(session, td, "DECISION_WINDOW_STALE", _now_iso)

        # 6. Exact end boundary — reject at or after prediction_window_end.
        if now >= _market_row.prediction_window_end:
            return await _reject_window(session, td, "PREDICTION_WINDOW_ENDED", _now_iso)

        # 7–9. Canonical lifecycle must be valid and WINDOW_LIVE.
        _lc = get_prediction_window_lifecycle(
            _market_row.prediction_window_start,
            _market_row.prediction_window_end,
            now=now,
        )
        if not _lc["valid"]:
            return await _reject_window(session, td, "INVALID_PREDICTION_WINDOW", _now_iso)
        if _lc["state"] != PRED_WINDOW_LIVE:
            return await _reject_window(session, td, "MARKET_NOT_WINDOW_LIVE", _now_iso)

        # ── Stale decision check ────────────────────────────────────────────────
        _max_age = settings.EXECUTION_MAX_DECISION_AGE_MINUTES
        if _max_age > 0 and td.decided_at is not None:
            _decided = (
                td.decided_at
                if td.decided_at.tzinfo is not None
                else td.decided_at.replace(tzinfo=timezone.utc)
            )
            _age_mins = (now - _decided).total_seconds() / 60.0
            if _age_mins > _max_age:
                logger.warning(
                    "Execution blocked: stale decision",
                    decision_id=td.id,
                    condition_id=td.condition_id,
                    asset=td.asset,
                    age_minutes=round(_age_mins, 1),
                    max_age_minutes=_max_age,
                    reject_reason="STALE_DECISION",
                )
                return None, True

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

        # ── Compute entry fee (Phase 4 Part D) ────────────────────────────────
        entry_fee_usdc = _compute_fee(fill_price, quantity)

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
            entry_fee_usdc=entry_fee_usdc,
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
            entry_fee_usdc=entry_fee_usdc,
        )

        return order, False
