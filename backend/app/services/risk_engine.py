"""
Risk Engine — Layers 9 + 14 + 16.

Screens PENDING OPEN_LONG_YES / OPEN_LONG_NO TradeDecision rows against a
set of trade-level and portfolio-level risk rules before they reach the
Execution Engine.

Pipeline position:
  Strategy Engine → [PENDING]
  → Risk Engine   → [RISK_APPROVED | BLOCKED]
  → Execution Engine executes RISK_APPROVED decisions only

Phase 12L: Position count is UNLIMITED.  No MAX_OPEN_POSITIONS,
PORTFOLIO_MAX_OPEN_POSITIONS, MAX_ENTRIES_PER_MARKET, MAX_OPEN_LOTS_PER_MARKET,
or MAX_SAME_SIDE_ENTRIES count caps.  Entry is gated solely by USDC exposure
and capital availability.

Layer 16 capital management gate (evaluated FIRST; short-circuits all other rules):
  0. DAILY_LOSS_LIMIT   — today's realized PnL <= -CAPITAL_DAILY_LOSS_LIMIT_USDC
  0. WEEKLY_LOSS_LIMIT  — this week's realized PnL <= -CAPITAL_WEEKLY_LOSS_LIMIT_USDC
  0. LOSS_STREAK_LIMIT  — consecutive closing losses >= CAPITAL_MAX_CONSECUTIVE_LOSSES
  0. MAX_DRAWDOWN_LIMIT — equity curve drawdown % >= CAPITAL_MAX_DRAWDOWN_PERCENT

Layer 9 rules (evaluated after Layer 16 passes; first failure wins):
  1a. OPPOSITE_SIDE_CONFLICT   — an open lot on the opposite side of this
                                 condition_id exists and ALLOW_OPPOSITE_SIDE_HEDGE
                                 is False.
  1e. MAX_EXPOSURE_PER_MARKET  — open USDC exposure in this condition_id would
                                 exceed MAX_EXPOSURE_PER_MARKET_USDC.
  1f. COOLDOWN_ACTIVE          — last entry for this condition_id was less
                                 than MIN_SECONDS_BETWEEN_ENTRIES ago.
  1g. SCALE_IN_NO_IMPROVEMENT  — second+ entry on this condition_id shows no
                                 measurable improvement over the previous
                                 confirmed (RISK_APPROVED / EXECUTED) entry:
                                 opportunity_score delta < SCALE_IN_MIN_OPPORTUNITY_DELTA
                                 AND yes_mid did not move ≥ SCALE_IN_ENTRY_PRICE_IMPROVEMENT
                                 in the favourable direction.
                                 First entries (no prior confirmed decision)
                                 always pass this rule.
  2. INSUFFICIENT_CAPITAL      — available_capital - proposed_notional
                                 < MIN_AVAILABLE_CAPITAL_RESERVE_USDC, where
                                 available_capital = CAPITAL_INITIAL_USDC
                                   + total_realized_pnl - current_open_exposure
  3. DAILY_LOSS                — sum of today's unrealized PnL <= MAX_DAILY_LOSS
  4. DAILY_TRADES              — orders placed today >= MAX_DAILY_TRADES

Layer 14 portfolio rules (evaluated after Layer 9; first failure wins):
  5. PORTFOLIO_EXPOSURE_LIMIT  — total USDC at risk would exceed portfolio cap
  6. ASSET_EXPOSURE_LIMIT      — USDC at risk in this asset would exceed asset cap

Settings (from config/settings.py):
  CAPITAL_DAILY_LOSS_LIMIT_USDC          float default 30.0
  CAPITAL_WEEKLY_LOSS_LIMIT_USDC         float default 75.0
  CAPITAL_MAX_CONSECUTIVE_LOSSES         int   default 5
  CAPITAL_MAX_DRAWDOWN_PERCENT           float default 20.0
  CAPITAL_ENABLE_KILL_SWITCH             bool  default True
  MIN_AVAILABLE_CAPITAL_RESERVE_USDC     float default 10.0
  MAX_DAILY_LOSS                         float default -50.0
  MAX_DAILY_TRADES                       int   default 500
  PORTFOLIO_MAX_EXPOSURE_USDC            float default 200.0
  PORTFOLIO_MAX_PER_ASSET_USDC           float default 100.0

CLOSE_POSITION decisions bypass ALL rules (Pass 2) — exits are never blocked.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.order import Order
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.repositories import risk_repository as risk_repo
from app.repositories import trade_decision_repository as td_repo
from app.utils.prediction_window import PRED_WINDOW_LIVE, get_prediction_window_lifecycle

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
            # Available capital: CAPITAL_INITIAL + realized_pnl - open_exposure.
            # Used by the INSUFFICIENT_CAPITAL rule (no count cap; pure $ gate).
            available_capital = await self._get_available_capital(session, open_positions)
            # Pre-fetch most recent confirmed entry per condition_id for the
            # SCALE_IN_NO_IMPROVEMENT delta gate (rule 1g).
            pending_cids = list({td.condition_id for td in pending})
            previous_entry_decisions = await self._get_previous_entry_decisions(
                session, pending_cids
            )
            # ── Batch-fetch MarketUniverse rows for all pending ENTRY CIDs ────
            # One query per cycle — never one query per decision.
            mu_result = await session.execute(
                select(MarketUniverse).where(
                    MarketUniverse.condition_id.in_(pending_cids)
                )
            )
            market_by_condition_id: dict = {
                m.condition_id: m for m in mu_result.scalars().all()
            }
            now = datetime.now(timezone.utc)

            # Running snapshots mutated in-memory as each decision in this batch
            # is approved — prevents a burst of N simultaneous decisions from all
            # passing exposure/capital caps against a stale pre-fetch.
            running_positions = list(open_positions)
            running_capital = available_capital  # decremented per approval

            for td in pending:
                try:
                    # ── Prediction window lifecycle gate (ENTRY only) ─────────
                    # Runs FIRST — before capital gate and all financial rules.
                    lc_block = self._check_entry_lifecycle_gate(
                        td, market_by_condition_id, started
                    )
                    if lc_block is not None:
                        block_reason: Optional[str] = lc_block
                    # Capital gate fires before financial rules
                    elif not capital_status.allowed:
                        block_reason = capital_status.reason
                    else:
                        block_reason = self._check_rules(
                            td=td,
                            open_positions=running_positions,
                            daily_trades=daily_trades,
                            daily_loss=daily_loss,
                            now=now,
                            previous_entry_decisions=previous_entry_decisions,
                            available_capital=running_capital,
                        )

                    if block_reason is None:
                        result_val = "ALLOW"
                        new_status = "RISK_APPROVED"
                        allowed += 1
                        incoming_usdc = td.position_size_usdc or 0.0
                        # Reflect this approval so later decisions in the same
                        # batch see the updated exposure and capital.
                        running_positions.append(
                            SimpleNamespace(
                                condition_id=td.condition_id,
                                side=td.decision.replace("OPEN_", ""),
                                asset=td.asset,
                                quantity=None,
                                remaining_quantity=incoming_usdc,
                                entry_price=1.0,
                                opened_at=now,
                            )
                        )
                        running_capital -= incoming_usdc
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
                        open_positions_count=len(running_positions),
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
        now: Optional[datetime] = None,
        previous_entry_decisions: Optional[dict] = None,
        available_capital: Optional[float] = None,
    ) -> Optional[str]:
        """
        Run all risk rules (market-entry Layer 9 + portfolio Layer 14).

        Phase 12L: no count-based position limits.  Enforcement is purely
        USDC-exposure-based and capital-availability-based.

        Layer 9 trade-level rules are evaluated first; the two Layer 14
        portfolio-level exposure rules run only when all Layer 9 rules pass.

        Returns the reason string for the first failing rule, or None if all
        rules pass (ALLOW).
        """
        now = now or datetime.now(timezone.utc)
        incoming_usdc: float = td.position_size_usdc or 0.0

        # ── Layer 9 rules ──────────────────────────────────────────────────────

        # Rule 1 — market-entry admission (side conflict, exposure, cooldown, delta)
        market_reason = self._check_market_entry_rules(
            td=td,
            open_positions=open_positions,
            now=now,
            incoming_usdc=incoming_usdc,
            previous_entry_decisions=previous_entry_decisions,
        )
        if market_reason is not None:
            return market_reason

        # Rule 2 — INSUFFICIENT_CAPITAL
        # available_capital = CAPITAL_INITIAL + realized_pnl - open_exposure
        # Entry not allowed when the reserve floor would be breached.
        if available_capital is not None:
            if available_capital - incoming_usdc < settings.MIN_AVAILABLE_CAPITAL_RESERVE_USDC:
                logger.info(
                    "Risk block: insufficient capital",
                    reason="INSUFFICIENT_CAPITAL",
                    asset=td.asset,
                    timeframe=td.timeframe,
                    available_capital=round(available_capital, 4),
                    incoming_usdc=incoming_usdc,
                    reserve=settings.MIN_AVAILABLE_CAPITAL_RESERVE_USDC,
                )
                return "INSUFFICIENT_CAPITAL"

        # Rule 3 — DAILY_LOSS limit
        if daily_loss <= settings.MAX_DAILY_LOSS:
            return "DAILY_LOSS"

        # Rule 4 — DAILY_TRADES limit
        if daily_trades >= settings.MAX_DAILY_TRADES:
            return "DAILY_TRADES"

        # ── Layer 14 portfolio exposure rules ───────────────────────────────────
        # All calculations use the in-memory running_positions list — no extra
        # DB round-trips.  position_size_usdc defaults to 0.0 for legacy rows.

        # Rule 5 — PORTFOLIO_EXPOSURE_LIMIT
        total_exposure = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else p.quantity or 0.0) * (p.entry_price or 0.0)
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

        # Rule 6 — ASSET_EXPOSURE_LIMIT
        asset_exposure = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else p.quantity or 0.0) * (p.entry_price or 0.0)
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

        return None

    @staticmethod
    def _check_market_entry_rules(
        td: TradeDecision,
        open_positions: list[Position],
        now: datetime,
        incoming_usdc: float,
        previous_entry_decisions: Optional[dict] = None,
        # lifetime_entry_counts accepted but ignored — count caps removed Phase 12L
        lifetime_entry_counts: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Market-entry admission rules for a single condition_id.

        Phase 12L: count caps (MAX_ENTRIES_PER_MARKET, MAX_OPEN_LOTS_PER_MARKET,
        MAX_SAME_SIDE_ENTRIES) removed.  Entry is now unlimited by count.

        Active rules:
          1a. OPPOSITE_SIDE_CONFLICT  — side-conflict protection.
          1e. MAX_EXPOSURE_PER_MARKET — USDC exposure cap per market.
          1f. COOLDOWN_ACTIVE         — spam-protection cooldown.
          1g. SCALE_IN_NO_IMPROVEMENT — delta gate for scale-in entries.
        """
        market_positions = [p for p in open_positions if p.condition_id == td.condition_id]

        # 1a — OPPOSITE_SIDE_CONFLICT
        if not settings.ALLOW_OPPOSITE_SIDE_HEDGE:
            opposite_open = any(p.side != td.decision.replace("OPEN_", "") for p in market_positions)
            if opposite_open:
                return "OPPOSITE_SIDE_CONFLICT"

        # 1e — MAX_EXPOSURE_PER_MARKET_USDC
        market_exposure = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else p.quantity or 0.0) * (p.entry_price or 0.0)
            for p in market_positions
        )
        if market_exposure + incoming_usdc > settings.MAX_EXPOSURE_PER_MARKET_USDC:
            return "MAX_EXPOSURE_PER_MARKET"

        # 1f — COOLDOWN_ACTIVE
        if market_positions and settings.MIN_SECONDS_BETWEEN_ENTRIES > 0:
            last_entry_at = max(p.opened_at for p in market_positions)
            if last_entry_at.tzinfo is None:
                last_entry_at = last_entry_at.replace(tzinfo=timezone.utc)
            elapsed = (now - last_entry_at).total_seconds()
            if elapsed < settings.MIN_SECONDS_BETWEEN_ENTRIES:
                return "COOLDOWN_ACTIVE"

        # 1g — SCALE_IN_NO_IMPROVEMENT (scale-in delta gate, Phase 12J)
        # Only fires for second+ entries (market_positions non-empty) when the
        # caller supplied a previous_entry_decisions lookup.
        # First entries always pass — no prior confirmed decision exists.
        if market_positions and previous_entry_decisions is not None:
            prev_td = previous_entry_decisions.get(td.condition_id)
            if prev_td is not None:
                improved = False

                # Criterion 1: opportunity_score improvement
                if (
                    td.opportunity_score is not None
                    and prev_td.opportunity_score is not None
                    and td.opportunity_score
                    >= prev_td.opportunity_score + settings.SCALE_IN_MIN_OPPORTUNITY_DELTA
                ):
                    improved = True

                # Criterion 2: favourable yes_mid movement (better entry price)
                if (
                    not improved
                    and td.yes_mid is not None
                    and prev_td.yes_mid is not None
                ):
                    if td.decision == "OPEN_LONG_YES":
                        # Cheaper YES contract → lower yes_mid is better
                        if prev_td.yes_mid - td.yes_mid >= settings.SCALE_IN_ENTRY_PRICE_IMPROVEMENT:
                            improved = True
                    elif td.decision == "OPEN_LONG_NO":
                        # Cheaper NO contract → higher yes_mid is better
                        if td.yes_mid - prev_td.yes_mid >= settings.SCALE_IN_ENTRY_PRICE_IMPROVEMENT:
                            improved = True

                if not improved:
                    return "SCALE_IN_NO_IMPROVEMENT"

        return None

    # ── Lifecycle gate ─────────────────────────────────────────────────────────

    @staticmethod
    def _check_entry_lifecycle_gate(
        td: TradeDecision,
        market_by_condition_id: dict,
        now: datetime,
    ) -> Optional[str]:
        """
        Validates that a pending ENTRY decision falls within an active prediction
        window (WINDOW_LIVE) before any capital or financial rules are evaluated.

        Checks in order:
          1. market row found in universe
          2. prediction_window_start present
          3. prediction_window_end present
          4. lifecycle metadata valid (e.g. duration exactly 300 s)
          5. current time < prediction_window_end (explicit end-time guard)
          6. lifecycle state == PRED_WINDOW_LIVE

        Returns the block-reason string for the first failing check, or None
        when all checks pass (gate open).

        Block codes:
          MARKET_NOT_IN_UNIVERSE    — condition_id absent from market_universe
          INVALID_PREDICTION_WINDOW — start/end missing or window metadata invalid
          PREDICTION_WINDOW_ENDED   — now >= prediction_window_end
          MARKET_NOT_WINDOW_LIVE    — state is UPCOMING, RESOLVING, etc.
        """
        market = market_by_condition_id.get(td.condition_id)
        if market is None:
            logger.info(
                "Risk lifecycle gate: market not in universe",
                condition_id=td.condition_id[:12],
                asset=td.asset,
                timeframe=td.timeframe,
                reason="MARKET_NOT_IN_UNIVERSE",
            )
            return "MARKET_NOT_IN_UNIVERSE"

        pw_start = market.prediction_window_start
        pw_end = market.prediction_window_end

        if pw_start is None or pw_end is None:
            logger.info(
                "Risk lifecycle gate: prediction window fields missing",
                condition_id=td.condition_id[:12],
                asset=td.asset,
                pw_start=pw_start,
                pw_end=pw_end,
                reason="INVALID_PREDICTION_WINDOW",
            )
            return "INVALID_PREDICTION_WINDOW"

        lc = get_prediction_window_lifecycle(pw_start, pw_end, now=now)

        if not lc["valid"]:
            logger.info(
                "Risk lifecycle gate: prediction window invalid",
                condition_id=td.condition_id[:12],
                asset=td.asset,
                lc_error=lc.get("validation_error"),
                reason="INVALID_PREDICTION_WINDOW",
            )
            return "INVALID_PREDICTION_WINDOW"

        # Explicit end-time guard — catches exact-end and post-end cases
        # with a dedicated block code distinct from the upstream state check.
        if now >= pw_end:
            logger.info(
                "Risk lifecycle gate: prediction window ended",
                condition_id=td.condition_id[:12],
                asset=td.asset,
                pw_end=pw_end.isoformat(),
                now=now.isoformat(),
                reason="PREDICTION_WINDOW_ENDED",
            )
            return "PREDICTION_WINDOW_ENDED"

        if lc["state"] != PRED_WINDOW_LIVE:
            logger.info(
                "Risk lifecycle gate: window not WINDOW_LIVE",
                condition_id=td.condition_id[:12],
                asset=td.asset,
                lc_state=lc["state"],
                reason="MARKET_NOT_WINDOW_LIVE",
            )
            return "MARKET_NOT_WINDOW_LIVE"

        return None

    # ── Shared DB queries ──────────────────────────────────────────────────────

    @staticmethod
    async def _get_previous_entry_decisions(
        session: AsyncSession,
        condition_ids: list[str],
    ) -> dict:
        """
        Return the most recent RISK_APPROVED / EXECUTED entry decision per
        condition_id, used by the SCALE_IN_NO_IMPROVEMENT gate (rule 1g).

        Delegates to the trade_decision_repository so query logic is co-located
        with other TradeDecision queries and is independently testable.
        """
        return await td_repo.get_previous_entry_decisions(session, condition_ids)

    @staticmethod
    async def _get_open_positions(session: AsyncSession) -> list[Position]:
        """Fetch all still-open lots (status OPEN or PARTIAL)."""
        result = await session.execute(
            select(Position).where(Position.status.in_(("OPEN", "PARTIAL")))
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_available_capital(
        session: AsyncSession,
        open_positions: list,
    ) -> float:
        """
        Compute available capital for new entries.

        available_capital = CAPITAL_INITIAL_USDC + total_realized_pnl - current_open_exposure

        Used by the INSUFFICIENT_CAPITAL rule to enforce a minimum reserve
        without relying on any position-count cap.
        """
        # Sum of realized PnL from ALL lots that have crystallised gains/losses:
        # both fully CLOSED lots and still-open PARTIAL lots (which accumulate
        # realized_pnl with every partial exit slice).
        result = await session.execute(
            select(func.coalesce(func.sum(Position.realized_pnl), 0.0))
            .where(
                Position.status.in_(["CLOSED", "PARTIAL"]),
                Position.realized_pnl.is_not(None),
            )
        )
        total_realized_pnl = float(result.scalar_one() or 0.0)

        # Current open exposure from the already-fetched open_positions list
        current_open_exposure = sum(
            (p.remaining_quantity if p.remaining_quantity is not None else getattr(p, "quantity", None) or 0.0)
            * (p.entry_price or 0.0)
            for p in open_positions
        )

        return settings.CAPITAL_INITIAL_USDC + total_realized_pnl - current_open_exposure

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
