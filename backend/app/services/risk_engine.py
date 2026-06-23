"""
Risk Engine — Layer 9.

Screens PENDING OPEN_LONG_YES / OPEN_LONG_NO TradeDecision rows against a
set of portfolio-level and market-level risk rules before they reach the
Execution Engine.

Pipeline position:
  Strategy Engine → [PENDING]
  → Risk Engine   → [RISK_APPROVED | BLOCKED]
  → Execution Engine executes RISK_APPROVED decisions only

Risk rules (evaluated in order; first failure wins):
  1. DUPLICATE_POSITION  — an OPEN position for the same condition_id exists
  2. MAX_OPEN_POSITIONS  — total OPEN positions >= MAX_OPEN_POSITIONS
  3. MAX_EXPOSURE        — OPEN positions for this asset >= MAX_EXPOSURE_PER_ASSET
  4. DAILY_LOSS          — sum of today's unrealized PnL <= MAX_DAILY_LOSS (negative)
  5. DAILY_TRADES        — orders placed today >= MAX_DAILY_TRADES

Settings (from config/settings.py):
  MAX_OPEN_POSITIONS     int   default 10
  MAX_EXPOSURE_PER_ASSET int   default 3
  MAX_DAILY_LOSS         float default -50.0
  MAX_DAILY_TRADES       int   default 20
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.order import Order
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.repositories import risk_repository as risk_repo

logger = get_logger(__name__)


class RiskEngine:
    """
    Evaluates PENDING TradeDecisions against portfolio risk rules.

    Usage (from background loop or FastAPI lifespan)::

        engine = RiskEngine()
        result = await engine.evaluate(session)
    """

    async def evaluate(self, session: AsyncSession) -> dict:
        """
        Run one full risk-check cycle.

        Fetches all PENDING OPEN_LONG_* decisions, runs every rule, and
        updates each decision's status to RISK_APPROVED or BLOCKED.

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
            logger.debug("Risk engine: no pending decisions to evaluate")
            return {
                "evaluated": 0,
                "allowed": 0,
                "blocked": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        # ── Pre-fetch shared risk state (single DB round-trip per cycle) ───────
        open_positions = await self._get_open_positions(session)
        daily_trades = await self._get_daily_trades_count(session)
        daily_loss = await self._get_daily_unrealized_loss(session)

        allowed = 0
        blocked = 0
        errors = 0

        for td in pending:
            try:
                block_reason = self._check_rules(
                    td=td,
                    open_positions=open_positions,
                    daily_trades=daily_trades,
                    daily_loss=daily_loss,
                )

                if block_reason is None:
                    result_val = "ALLOW"
                    new_status = "RISK_APPROVED"
                    allowed += 1
                else:
                    result_val = "BLOCK"
                    new_status = "BLOCKED"
                    blocked += 1

                # ── Persist risk event ─────────────────────────────────────────
                await risk_repo.create_risk_event(
                    session,
                    decision_id=td.id,
                    condition_id=td.condition_id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    result=result_val,
                    reason=block_reason,
                    open_positions_count=len(open_positions),
                    daily_loss=daily_loss,
                    daily_trades=daily_trades,
                )

                # ── Update trade decision status ───────────────────────────────
                td.status = new_status

                logger.info(
                    "Risk evaluation complete",
                    decision_id=td.id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    result=result_val,
                    reason=block_reason,
                )

            except Exception as exc:
                logger.error(
                    "Risk engine error",
                    decision_id=td.id,
                    asset=td.asset,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        logger.info(
            "Risk engine cycle complete",
            evaluated=len(pending),
            allowed=allowed,
            blocked=blocked,
            errors=errors,
            duration_ms=elapsed_ms,
        )

        return {
            "evaluated": len(pending),
            "allowed": allowed,
            "blocked": blocked,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    # ── Rule checks ────────────────────────────────────────────────────────────

    def _check_rules(
        self,
        td: TradeDecision,
        open_positions: list[Position],
        daily_trades: int,
        daily_loss: float,
    ) -> Optional[str]:
        """
        Run all five risk rules.

        Returns the reason string for the first failing rule, or None if all
        rules pass (ALLOW).
        """
        # Rule 1 — DUPLICATE_POSITION
        if self._is_duplicate(td, open_positions):
            return "DUPLICATE_POSITION"

        # Rule 2 — MAX_OPEN_POSITIONS
        if len(open_positions) >= settings.MAX_OPEN_POSITIONS:
            return "MAX_OPEN_POSITIONS"

        # Rule 3 — MAX_EXPOSURE (positions per asset)
        asset_positions = [p for p in open_positions if p.asset == td.asset]
        if len(asset_positions) >= settings.MAX_EXPOSURE_PER_ASSET:
            return "MAX_EXPOSURE"

        # Rule 4 — DAILY_LOSS limit
        if daily_loss <= settings.MAX_DAILY_LOSS:
            return "DAILY_LOSS"

        # Rule 5 — DAILY_TRADES limit
        if daily_trades >= settings.MAX_DAILY_TRADES:
            return "DAILY_TRADES"

        return None

    @staticmethod
    def _is_duplicate(td: TradeDecision, open_positions: list[Position]) -> bool:
        """Return True if there is already an OPEN position for this condition_id."""
        return any(p.condition_id == td.condition_id for p in open_positions)

    # ── Shared DB queries ──────────────────────────────────────────────────────

    @staticmethod
    async def _get_open_positions(session: AsyncSession) -> list[Position]:
        """Fetch all currently OPEN positions."""
        result = await session.execute(
            select(Position).where(Position.status == "OPEN")
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_daily_trades_count(session: AsyncSession) -> int:
        """Count orders created since midnight UTC today."""
        from sqlalchemy import cast, Date
        today = datetime.now(timezone.utc).date()
        result = await session.execute(
            select(func.count(Order.id))
            .where(cast(Order.created_at, Date) == today)
        )
        return result.scalar_one() or 0

    @staticmethod
    async def _get_daily_unrealized_loss(session: AsyncSession) -> float:
        """Return the sum of unrealized PnL across all OPEN positions."""
        result = await session.execute(
            select(func.coalesce(func.sum(Position.unrealized_pnl), 0.0))
            .where(
                Position.status == "OPEN",
                Position.unrealized_pnl.is_not(None),
            )
        )
        return float(result.scalar_one() or 0.0)
