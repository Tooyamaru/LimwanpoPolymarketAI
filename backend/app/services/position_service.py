"""
Position Service — Layer 8: Position Tracking.

Manages the full lifecycle of paper-mode positions:

  1. create_position_from_fill()
       Called after Execution Engine creates a FILLED order.
       Reads any FILLED orders that do not yet have a Position row and
       creates one per fill.

  2. update_market_prices()
       Fetches the latest yes_mid from the opportunities table for each
       OPEN position's condition_id and computes current_price:
         LONG_YES → current_price = yes_mid
         LONG_NO  → current_price = 1 - yes_mid

  3. recalculate_pnl()
       Recomputes unrealized_pnl for every OPEN position:
         unrealized_pnl = quantity * (current_price - entry_price)

  4. close_position()
       Marks a position CLOSED, sets realized_pnl, clears unrealized_pnl.

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
          3. Recompute unrealized_pnl for all OPEN positions.

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
        Create Position rows for FILLED orders that don't yet have one.

        Returns the number of new positions created.
        """
        filled_orders_stmt = (
            select(Order)
            .where(Order.status == "FILLED")
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
            )
            created += 1
            logger.info(
                "Position opened from fill",
                order_id=order.id,
                asset=order.asset,
                timeframe=order.timeframe,
                side=order.side,
                entry_price=order.filled_price,
            )

        return created

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

        Returns the number of positions recalculated.
        """
        open_positions = await repo.get_open_positions(session)
        recalculated = 0

        for pos in open_positions:
            if pos.current_price is None:
                continue

            upnl = round(pos.quantity * (pos.current_price - pos.entry_price), 6)
            await session.execute(
                update(pos_model.Position)
                .where(pos_model.Position.id == pos.id)
                .values(unrealized_pnl=upnl)
            )
            recalculated += 1

        return recalculated

    async def close_position(
        self,
        session: AsyncSession,
        position_id: int,
        closing_price: Optional[float] = None,
    ) -> Optional[object]:
        """
        Close a position: mark CLOSED, compute realized_pnl, clear unrealized.

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
        realized = None
        if close_px is not None:
            realized = round(pos.quantity * (close_px - pos.entry_price), 6)

        now = datetime.now(timezone.utc)
        await session.execute(
            update(pos_model.Position)
            .where(pos_model.Position.id == pos.id)
            .values(
                status="CLOSED",
                current_price=close_px,
                unrealized_pnl=None,
                realized_pnl=realized,
                closed_at=now,
            )
        )
        await session.commit()

        logger.info(
            "Position closed",
            position_id=position_id,
            asset=pos.asset,
            timeframe=pos.timeframe,
            side=pos.side,
            entry_price=pos.entry_price,
            close_price=close_px,
            realized_pnl=realized,
        )
        return pos
