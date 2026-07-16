"""
Position Service — Layer 8: Position Tracking.

Manages the full lifecycle of paper-mode positions:

  1. create_position_from_fill()
       Called after Execution Engine creates a FILLED order.
       Reads any FILLED orders that do not yet have a Position row and
       creates one per fill.  Sets total_fee_usdc = order.entry_fee_usdc.

  2. update_market_prices()
       Fetches the latest yes_mid from the opportunities table for each
       OPEN position's condition_id and computes current_price:
         LONG_YES → current_price = yes_mid
         LONG_NO  → current_price = 1 - yes_mid

  3. recalculate_pnl()
       Recomputes unrealized_pnl for every OPEN position that has a
       current_price set.  Also maintains peak_pnl_usdc for trailing stop
       (Phase 4 Part E):
         unrealized_pnl = quantity * (current_price - entry_price)
         peak_pnl_usdc  = max(peak_pnl_usdc, unrealized_pnl)

  4. close_position()
       Marks a position CLOSED, computes realized_pnl deducting total fees:
         realized_pnl = quantity * (exit_price - entry_price) - total_fee_usdc
       Clears unrealized_pnl.

Background loop runs every POSITION_TRACKING_INTERVAL_SECONDS (30 s).
Each cycle: create_position_from_fill → update_market_prices → recalculate_pnl.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.order import Order
from app.models.opportunity import Opportunity
from app.models import position as pos_model
from app.repositories import position_repository as repo

logger = get_logger(__name__)


class PositionService:
    """
    Manages paper-mode positions derived from FILLED orders.

    Usage (from FastAPI lifespan or background loop)::

        svc = PositionService()
        result = await svc.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        """
        Execute one full position-tracking cycle.

        Steps:
          1. Create positions for any new FILLED orders.
          2. Refresh current_price from latest opportunity data.
          3. Recompute unrealized_pnl and peak_pnl_usdc for all OPEN positions.

        Returns a dict with cycle summary statistics.
        """
        created = await self.create_position_from_fill(session)
        # Flush so newly created positions are visible to the price/PnL queries
        # within the same session (autoflush=False on the session factory).
        await session.flush()
        updated = await self.update_market_prices(session)
        recalculated = await self.recalculate_pnl(session)
        await session.commit()

        logger.info(
            "Position tracking cycle complete",
            positions_created=created,
            prices_updated=updated,
            pnl_recalculated=recalculated,
        )
        return {
            "positions_created": created,
            "prices_updated": updated,
            "pnl_recalculated": recalculated,
        }

    async def create_position_from_fill(self, session: AsyncSession) -> int:
        """
        Create Position rows for FILLED entry orders that don't yet have one.

        Only entry orders (side LONG_YES / LONG_NO) create positions.
        Exit orders (side SELL_YES / SELL_NO) are skipped — they are linked
        back to existing positions via Position.close_order_id.

        Phase 4 Part D: sets total_fee_usdc = order.entry_fee_usdc.

        Returns the number of new positions created.
        """
        filled_orders_stmt = (
            select(Order)
            .where(
                Order.status == "FILLED",
                Order.side.in_(["LONG_YES", "LONG_NO"]),
            )
            .order_by(Order.filled_at)
        )
        result = await session.execute(filled_orders_stmt)
        filled_orders: list[Order] = list(result.scalars().all())

        if not filled_orders:
            return 0

        created = 0
        for order in filled_orders:
            existing = await repo.get_position_by_order(session, order.id)
            if existing is not None:
                continue

            if order.filled_price is None:
                logger.warning(
                    "Position skipped: filled_price missing",
                    order_id=order.id,
                    asset=order.asset,
                )
                continue

            # Seed total_fee_usdc with the entry fee from the order
            entry_fee = float(getattr(order, "entry_fee_usdc", None) or 0.0)

            # Multi-entry bookkeeping: this lot's sequence number and, for
            # sequence > 1, a heuristic reason for the additional entry.
            prior_lots = await repo.get_positions_for_condition(session, order.condition_id)
            entry_sequence = len(prior_lots) + 1
            scale_in_reason = self._infer_scale_in_reason(
                prior_lots=prior_lots, new_entry_price=order.filled_price,
            ) if entry_sequence > 1 else None

            await repo.create_position(
                session,
                order_id=order.id,
                condition_id=order.condition_id,
                asset=order.asset,
                timeframe=order.timeframe,
                side=order.side,
                quantity=order.quantity,
                entry_price=order.filled_price,
                opened_at=order.filled_at or datetime.now(timezone.utc),
                total_fee_usdc=entry_fee,
                entry_sequence=entry_sequence,
                scale_in_reason=scale_in_reason,
            )
            created += 1
            logger.info(
                "Position opened from fill",
                order_id=order.id,
                asset=order.asset,
                timeframe=order.timeframe,
                side=order.side,
                entry_price=order.filled_price,
                entry_fee_usdc=entry_fee,
                entry_sequence=entry_sequence,
                scale_in_reason=scale_in_reason,
            )

        return created

    @staticmethod
    def _infer_scale_in_reason(prior_lots: list, new_entry_price: float) -> str:
        """
        Heuristic reason for a sequence > 1 lot. No upstream engine currently
        tags *why* the strategy re-entered a market it already holds, so this
        derives a best-effort label from observable lot history:

          REENTRY_AFTER_PARTIAL_EXIT — the most recent lot for this market was
                                        fully closed before this new fill
          BETTER_ENTRY_PRICE         — this fill is priced better (lower cost
                                        per contract) than the average of the
                                        currently still-open lots
          SIGNAL_STRENGTHENED        — default: strategy re-signalled while
                                        prior lot(s) remain open at a similar
                                        or worse price
        """
        if not prior_lots:
            return "SIGNAL_STRENGTHENED"

        most_recent = prior_lots[-1]
        if most_recent.status == "CLOSED":
            return "REENTRY_AFTER_PARTIAL_EXIT"

        still_open = [p for p in prior_lots if p.status in ("OPEN", "PARTIAL")]
        if still_open:
            avg_open_price = sum(p.entry_price for p in still_open) / len(still_open)
            if new_entry_price < avg_open_price:
                return "BETTER_ENTRY_PRICE"

        return "SIGNAL_STRENGTHENED"

    async def update_market_prices(self, session: AsyncSession) -> int:
        """
        Refresh current_price for all OPEN positions using the latest
        yes_mid from the opportunities table.

          LONG_YES → current_price = yes_mid
          LONG_NO  → current_price = 1 - yes_mid

        Returns the number of positions updated.
        """
        open_positions = await repo.get_open_positions(session)
        if not open_positions:
            return 0

        condition_ids = list({p.condition_id for p in open_positions})
        opp_result = await session.execute(
            select(Opportunity.condition_id, Opportunity.yes_mid)
            .where(Opportunity.condition_id.in_(condition_ids))
        )
        mid_map: dict[str, Optional[float]] = {
            row[0]: row[1] for row in opp_result.all()
        }

        updated = 0
        for pos in open_positions:
            yes_mid = mid_map.get(pos.condition_id)
            if yes_mid is None:
                continue

            if pos.side == "LONG_YES":
                current_price = round(yes_mid, 6)
            else:
                current_price = round(1.0 - yes_mid, 6)

            await session.execute(
                update(pos_model.Position)
                .where(pos_model.Position.id == pos.id)
                .values(current_price=current_price)
            )
            updated += 1

        return updated

    async def recalculate_pnl(self, session: AsyncSession) -> int:
        """
        Recompute unrealized_pnl for all OPEN positions that have a
        current_price set.

          unrealized_pnl = quantity * (current_price - entry_price)

        Phase 4 Part E (trailing stop):
          If unrealized_pnl > peak_pnl_usdc (or peak is not yet set),
          update peak_pnl_usdc to the new high-water mark.

        Returns the number of positions recalculated.
        """
        open_positions = await repo.get_open_positions(session)
        recalculated = 0

        for pos in open_positions:
            if pos.current_price is None:
                continue

            qty = pos.remaining_quantity if pos.remaining_quantity is not None else pos.quantity
            upnl = round(qty * (pos.current_price - pos.entry_price), 6)

            # Maintain peak PnL for trailing stop (Phase 4 Part E)
            current_peak = getattr(pos, "peak_pnl_usdc", None)
            new_peak = upnl if (current_peak is None or upnl > current_peak) else current_peak

            await session.execute(
                update(pos_model.Position)
                .where(pos_model.Position.id == pos.id)
                .values(unrealized_pnl=upnl, peak_pnl_usdc=new_peak)
            )
            recalculated += 1

        return recalculated

    async def close_position(
        self,
        session: AsyncSession,
        position_id: int,
        closing_price: Optional[float] = None,
        close_reason: Optional[str] = None,
        close_decision_id: Optional[int] = None,
        close_order_id: Optional[int] = None,
        exit_fee_usdc: Optional[float] = None,
        close_quantity: Optional[float] = None,
    ) -> Optional[object]:
        """
        Close all or part of a lot's remaining_quantity.

        close_quantity semantics:
          None or >= remaining_quantity → full close: status CLOSED,
              remaining_quantity -> 0, unrealized_pnl cleared.
          0 < close_quantity < remaining_quantity → partial close: status
              PARTIAL, remaining_quantity decremented, closed_at stays unset,
              realized_pnl accumulates this slice's PnL on top of any prior
              partial closes of the same lot.

        Phase 4 Part D (fee simulation):
          total_fee_usdc accumulates entry_fee_usdc (already set) + every
          exit_fee_usdc passed to each close_position() call on this lot.
          realized_pnl (this call) = close_qty * (exit_price - entry_price) - exit_fee_usdc,
          added to whatever realized_pnl the lot already carried.

        Layer 12 audit trail:
          close_reason      — why this close happened
          close_decision_id — TradeDecision.id that triggered the close
          close_order_id    — Order.id of the exit fill (most recent one)

        If closing_price is None, uses current_price as the close price.
        Returns the updated Position or None if not found.
        """
        pos = await repo.get_position(session, position_id)
        if pos is None:
            logger.warning("close_position: position not found", position_id=position_id)
            return None

        if pos.status == "CLOSED":
            logger.warning("close_position: already CLOSED", position_id=position_id)
            return pos

        close_px = closing_price if closing_price is not None else pos.current_price

        remaining = pos.remaining_quantity if pos.remaining_quantity is not None else pos.quantity
        if close_quantity is None or close_quantity >= remaining - 1e-9:
            close_qty = remaining
        elif close_quantity <= 0:
            logger.warning(
                "close_position: close_quantity must be positive, treating as full close",
                position_id=position_id, close_quantity=close_quantity,
            )
            close_qty = remaining
        else:
            close_qty = close_quantity

        new_remaining = round(remaining - close_qty, 8)
        is_full_close = new_remaining <= 1e-9

        # Fees accumulate across every partial close of this lot
        prior_fee = float(getattr(pos, "total_fee_usdc", None) or 0.0)
        this_exit_fee = float(exit_fee_usdc or 0.0)
        total_fee = round(prior_fee + this_exit_fee, 6)

        # Realized PnL accumulates across every partial close of this lot
        prior_realized = float(getattr(pos, "realized_pnl", None) or 0.0)
        slice_pnl = None
        if close_px is not None:
            slice_pnl = close_qty * (close_px - pos.entry_price) - this_exit_fee
        new_realized = round(prior_realized + slice_pnl, 6) if slice_pnl is not None else (
            float(getattr(pos, "realized_pnl", None) or 0.0) or None
        )

        now = datetime.now(timezone.utc)
        values: dict = {
            "remaining_quantity": 0.0 if is_full_close else new_remaining,
            "status": "CLOSED" if is_full_close else "PARTIAL",
            "current_price": close_px,
            "realized_pnl": new_realized,
            "exit_price": close_px,
            "close_reason": close_reason,
            "close_decision_id": close_decision_id,
            "close_order_id": close_order_id,
            "total_fee_usdc": total_fee,
        }
        if is_full_close:
            values["unrealized_pnl"] = None
            values["closed_at"] = now
        else:
            # Still-open remainder keeps accruing unrealized PnL on the next
            # recalculate_pnl() pass against the reduced remaining_quantity.
            values["unrealized_pnl"] = (
                round(new_remaining * (close_px - pos.entry_price), 6) if close_px is not None else None
            )

        await session.execute(
            update(pos_model.Position)
            .where(pos_model.Position.id == pos.id)
            .values(**values)
        )
        await session.commit()

        logger.info(
            "Position lot closed" if is_full_close else "Position lot partially closed",
            position_id=position_id,
            asset=pos.asset,
            timeframe=pos.timeframe,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=close_px,
            close_quantity=close_qty,
            remaining_quantity=values["remaining_quantity"],
            total_fee_usdc=total_fee,
            realized_pnl=new_realized,
            close_reason=close_reason,
            close_decision_id=close_decision_id,
            close_order_id=close_order_id,
        )
        return pos
