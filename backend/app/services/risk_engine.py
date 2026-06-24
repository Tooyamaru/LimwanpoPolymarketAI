"""
Risk Engine — Layers 9 + 14 + 16.

Screens PENDING OPEN_LONG_YES / OPEN_LONG_NO TradeDecision rows against a
set of trade-level and portfolio-level risk rules before they reach the
Execution Engine.

Pipeline position:
  Strategy Engine → [PENDING]
  → Risk Engine   → [RISK_APPROVED | BLOCKED]
  → Execution Engine executes RISK_APPROVED decisions only

Layer 16 capital management gate (evaluated FIRST; short-circuits all other rules):
  0. DAILY_LOSS_LIMIT   — today's realized PnL <= -CAPITAL_DAILY_LOSS_LIMIT_USDC
  0. WEEKLY_LOSS_LIMIT  — this week's realized PnL <= -CAPITAL_WEEKLY_LOSS_LIMIT_USDC
  0. LOSS_STREAK_LIMIT  — consecutive closing losses >= CAPITAL_MAX_CONSECUTIVE_LOSSES
  0. MAX_DRAWDOWN_LIMIT — equity curve drawdown % >= CAPITAL_MAX_DRAWDOWN_PERCENT

Layer 9 rules (evaluated after Layer 16 passes; first failure wins):
  1. DUPLICATE_POSITION  — an OPEN position for the same condition_id exists
  2. MAX_OPEN_POSITIONS  — total OPEN positions >= MAX_OPEN_POSITIONS
  3. MAX_EXPOSURE        — OPEN positions for this asset >= MAX_EXPOSURE_PER_ASSET
  4. DAILY_LOSS          — sum of today's unrealized PnL <= MAX_DAILY_LOSS (negative)
  5. DAILY_TRADES        — orders placed today >= MAX_DAILY_TRADES

Layer 14 portfolio rules (evaluated after Layer 9; first failure wins):
  6. PORTFOLIO_EXPOSURE_LIMIT       — total USDC at risk would exceed portfolio cap
  7. PORTFOLIO_POSITION_LIMIT       — total open positions would exceed portfolio cap
  8. ASSET_EXPOSURE_LIMIT           — USDC at risk in this asset would exceed asset cap
  9. TIMEFRAME_POSITION_LIMIT       — open positions in this timeframe >= timeframe cap

Settings (from config/settings.py):
  CAPITAL_DAILY_LOSS_LIMIT_USDC         float default 30.0
  CAPITAL_WEEKLY_LOSS_LIMIT_USDC        float default 75.0
  CAPITAL_MAX_CONSECUTIVE_LOSSES        int   default 5
  CAPITAL_MAX_DRAWDOWN_PERCENT          float default 20.0
  CAPITAL_ENABLE_KILL_SWITCH            bool  default True
  MAX_OPEN_POSITIONS                    int   default 10
  MAX_EXPOSURE_PER_ASSET                int   default 3
  MAX_DAILY_LOSS                        float default -50.0
  MAX_DAILY_TRADES                      int   default 20
  PORTFOLIO_MAX_EXPOSURE_USDC           float default 200.0
  PORTFOLIO_MAX_OPEN_POSITIONS          int   default 5
  PORTFOLIO_MAX_PER_ASSET_USDC          float default 100.0
  PORTFOLIO_MAX_PER_TIMEFRAME_POSITIONS int   default 3

CLOSE_POSITION decisions bypass ALL rules (Pass 2) — exits are never blocked.
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

        Pass 1 — Entry decisions (OPEN_LONG_YES / OPEN_LONG_NO):
          Fetches all PENDING entry decisions, runs all five risk rules, and
          marks each RISK_APPROVED or BLOCKED.

        Pass 2 — Exit decisions (CLOSE_POSITION):
          Fetches all PENDING exit decisions and auto-approves them without
          evaluating any risk rules.  Exit decisions are never blocked.

        Returns
        -------
        dict with cycle summary statistics.
        """
        started = datetime.now(timezone.utc)

        # ── Pass 1: PENDING entry decisions ────────────────────────────────────
        result = await session.execute(
            select(TradeDecision)
            .where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "PENDING",
            )
            .order_by(TradeDecision.decided_at)
        )
        pending: list[TradeDecision] = list(result.scalars().all())

        allowed = 0
        blocked = 0
        errors = 0

        if pending:
            # ── Layer 16: Capital management gate (one check covers all decisions) ─
            from app.services.capital_management_service import CapitalManagementService
            capital_svc = CapitalManagementService()
            capital_status = await capital_svc.evaluate(session)

            # ── Pre-fetch shared risk state (single DB round-trip per cycle) ─────
            open_positions = await self._get_open_positions(session)
            daily_trades = await self._get_daily_trades_count(session)
            daily_loss = await self._get_daily_unrealized_loss(session)

            for td in pending:
                try:
                    # Capital gate fires before all other rules
                    if not capital_status.allowed:
                        block_reason: Optional[str] = capital_status.reason
                    else:
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

                    # ── Persist risk event ─────────────────────────────────────
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

                    # ── Update trade decision status ───────────────────────────
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
        else:
            logger.debug("Risk engine: no pending entry decisions")

        # ── Pass 2: PENDING exit decisions (CLOSE_POSITION) ────────────────────
        # Exit decisions are always approved — no risk rules are evaluated.
        exit_result = await session.execute(
            select(TradeDecision)
            .where(
                TradeDecision.decision == "CLOSE_POSITION",
                TradeDecision.status == "PENDING",
            )
            .order_by(TradeDecision.decided_at)
        )
        pending_exits: list[TradeDecision] = list(exit_result.scalars().all())

        exit_approved = 0
        for td in pending_exits:
            try:
                td.status = "RISK_APPROVED"
                await risk_repo.create_risk_event(
                    session,
                    decision_id=td.id,
                    condition_id=td.condition_id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    result="ALLOW",
                    reason=None,
                    open_positions_count=0,
                    daily_loss=0.0,
                    daily_trades=0,
                )
                exit_approved += 1
                logger.info(
                    "Exit decision auto-approved",
                    decision_id=td.id,
                    asset=td.asset,
                    timeframe=td.timeframe,
                    exit_reason=td.exit_reason,
                )
            except Exception as exc:
                logger.error(
                    "Risk engine error (exit path)",
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
            exit_approved=exit_approved,
            errors=errors,
            duration_ms=elapsed_ms,
        )

        return {
            "evaluated": len(pending),
            "allowed": allowed,
            "blocked": blocked,
            "exit_approved": exit_approved,
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
        Run all nine risk rules (Layer 9 + Layer 14).

        Layer 9 trade-level rules are evaluated first; the four Layer 14
        portfolio-level rules run only when all Layer 9 rules pass.

        Returns the reason string for the first failing rule, or None if all
        rules pass (ALLOW).
        """
        # ── Layer 9 rules ──────────────────────────────────────────────────────

        # Rule 1 — DUPLICATE_POSITION
        if self._is_duplicate(td, open_positions):
            return "DUPLICATE_POSITION"

        # Rule 2 — MAX_OPEN_POSITIONS
        if len(open_positions) >= settings.MAX_OPEN_POSITIONS:
            return "MAX_OPEN_POSITIONS"

        # Rule 3 — MAX_EXPOSURE (positions per asset, by count)
        asset_positions = [p for p in open_positions if p.asset == td.asset]
        if len(asset_positions) >= settings.MAX_EXPOSURE_PER_ASSET:
            return "MAX_EXPOSURE"

        # Rule 4 — DAILY_LOSS limit
        if daily_loss <= settings.MAX_DAILY_LOSS:
            return "DAILY_LOSS"

        # Rule 5 — DAILY_TRADES limit
        if daily_trades >= settings.MAX_DAILY_TRADES:
            return "DAILY_TRADES"

        # ── Layer 14 portfolio rules ────────────────────────────────────────────
        # All calculations use the pre-fetched open_positions list — no extra
        # DB round-trips.  position_size_usdc defaults to 0.0 for legacy rows.

        incoming_usdc: float = td.position_size_usdc or 0.0

        # Rule 6 — PORTFOLIO_EXPOSURE_LIMIT
        total_exposure = sum(
            (p.quantity or 0.0) * (p.entry_price or 0.0)
            for p in open_positions
        )
        if total_exposure + incoming_usdc > settings.PORTFOLIO_MAX_EXPOSURE_USDC:
            logger.info(
                "Portfolio risk block",
                reason="PORTFOLIO_EXPOSURE_LIMIT",
                asset=td.asset,
                timeframe=td.timeframe,
                current_exposure=round(total_exposure, 4),
                incoming_usdc=incoming_usdc,
                limit=settings.PORTFOLIO_MAX_EXPOSURE_USDC,
            )
            return "PORTFOLIO_EXPOSURE_LIMIT"

        # Rule 7 — PORTFOLIO_POSITION_LIMIT
        if len(open_positions) >= settings.PORTFOLIO_MAX_OPEN_POSITIONS:
            logger.info(
                "Portfolio risk block",
                reason="PORTFOLIO_POSITION_LIMIT",
                asset=td.asset,
                timeframe=td.timeframe,
                open_positions=len(open_positions),
                limit=settings.PORTFOLIO_MAX_OPEN_POSITIONS,
            )
            return "PORTFOLIO_POSITION_LIMIT"

        # Rule 8 — ASSET_EXPOSURE_LIMIT
        asset_exposure = sum(
            (p.quantity or 0.0) * (p.entry_price or 0.0)
            for p in open_positions
            if p.asset == td.asset
        )
        if asset_exposure + incoming_usdc > settings.PORTFOLIO_MAX_PER_ASSET_USDC:
            logger.info(
                "Portfolio risk block",
                reason="ASSET_EXPOSURE_LIMIT",
                asset=td.asset,
                timeframe=td.timeframe,
                asset_exposure=round(asset_exposure, 4),
                incoming_usdc=incoming_usdc,
                limit=settings.PORTFOLIO_MAX_PER_ASSET_USDC,
            )
            return "ASSET_EXPOSURE_LIMIT"

        # Rule 9 — TIMEFRAME_POSITION_LIMIT
        timeframe_count = sum(
            1 for p in open_positions if p.timeframe == td.timeframe
        )
        if timeframe_count >= settings.PORTFOLIO_MAX_PER_TIMEFRAME_POSITIONS:
            logger.info(
                "Portfolio risk block",
                reason="TIMEFRAME_POSITION_LIMIT",
                asset=td.asset,
                timeframe=td.timeframe,
                timeframe_count=timeframe_count,
                limit=settings.PORTFOLIO_MAX_PER_TIMEFRAME_POSITIONS,
            )
            return "TIMEFRAME_POSITION_LIMIT"

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
