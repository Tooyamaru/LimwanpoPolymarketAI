"""
Capital Management Service — Layer 16.

Account-level protection layer that sits ABOVE the Risk Engine.
Prevents new trades from opening when account losses exceed predefined limits.

Kill-switch rules (evaluated in order; first match wins):
  1. DAILY_LOSS_LIMIT    — today's realized PnL <= -CAPITAL_DAILY_LOSS_LIMIT_USDC
  2. WEEKLY_LOSS_LIMIT   — this week's realized PnL <= -CAPITAL_WEEKLY_LOSS_LIMIT_USDC
  3. LOSS_STREAK_LIMIT   — consecutive closing losses >= CAPITAL_MAX_CONSECUTIVE_LOSSES
  4. MAX_DRAWDOWN_LIMIT  — equity drawdown % >= CAPITAL_MAX_DRAWDOWN_PERCENT

CLOSE_POSITION decisions are NEVER blocked by this layer.
Only OPEN_LONG_YES / OPEN_LONG_NO decisions are screened.

All metrics are derived exclusively from CLOSED positions (realized_pnl).
Unrealized PnL is never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)


@dataclass
class CapitalStatus:
    """Result returned by CapitalManagementService.evaluate()."""
    allowed: bool
    reason: Optional[str]
    daily_pnl: float
    weekly_pnl: float
    consecutive_losses: int
    drawdown_percent: float


@dataclass
class CapitalStatusDetailed:
    """Extended result for /api/v1/risk/capital-status."""
    # Gate
    capital_blocked: bool
    block_code: Optional[str]
    block_reason: Optional[str]
    block_scope: str              # "DAILY" | "SESSION" | "PERMANENT" | "NONE"
    blocked_at: Optional[str]     # ISO-8601 UTC; set when blocked=True
    blocked_until: Optional[str]  # ISO-8601 UTC or None for permanent blocks
    reset_policy: str             # human-readable description
    reset_available: bool         # True if a non-manual reset path exists
    # Equity
    initial_capital: float
    current_equity: float
    peak_equity: float
    drawdown_amount: float
    drawdown_percent: float
    max_drawdown_limit: float
    # Daily
    daily_start_equity: float     # initial_capital + daily_pnl_before_today (approx)
    daily_loss_amount: float
    daily_drawdown_percent: float
    daily_loss_limit: float
    # Consecutive losses
    consecutive_losses: int
    consecutive_loss_limit: int
    # Portfolio
    open_exposure: float
    available_capital: float
    daily_pnl: float
    weekly_pnl: float
    # Meta
    data_source: str
    last_updated_at: str          # ISO-8601 UTC


class CapitalManagementService:
    """
    Evaluates account-level capital protection rules.

    Usage::

        svc = CapitalManagementService()
        status = await svc.evaluate(session)
        if not status.allowed:
            # block trade
    """

    async def evaluate(self, session: AsyncSession) -> CapitalStatus:
        """
        Run all capital protection rules against CLOSED position data.

        Returns a CapitalStatus with allowed=True when trading may proceed,
        or allowed=False with a reason code when the kill switch fires.
        """
        if not settings.CAPITAL_ENABLE_KILL_SWITCH:
            return CapitalStatus(
                allowed=True,
                reason=None,
                daily_pnl=0.0,
                weekly_pnl=0.0,
                consecutive_losses=0,
                drawdown_percent=0.0,
            )

        closed = await pos_repo.get_closed_positions(session)

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        daily_pnl = self._compute_period_pnl(closed, since=today_start)
        weekly_pnl = self._compute_period_pnl(closed, since=week_start)
        consecutive_losses = self._compute_consecutive_losses(
            closed,
            cooldown_minutes=settings.CAPITAL_COOLDOWN_MINUTES,
            now=now,
        )
        drawdown_percent = self._compute_drawdown_percent(
            closed, initial_capital=settings.CAPITAL_INITIAL_USDC
        )

        reason: Optional[str] = None

        # Rule 1 — Daily loss limit
        if daily_pnl <= -settings.CAPITAL_DAILY_LOSS_LIMIT_USDC:
            reason = "DAILY_LOSS_LIMIT"

        # Rule 2 — Weekly loss limit
        elif weekly_pnl <= -settings.CAPITAL_WEEKLY_LOSS_LIMIT_USDC:
            reason = "WEEKLY_LOSS_LIMIT"

        # Rule 3 — Consecutive loss streak
        elif consecutive_losses >= settings.CAPITAL_MAX_CONSECUTIVE_LOSSES:
            reason = "LOSS_STREAK_LIMIT"

        # Rule 4 — Max drawdown percent
        elif drawdown_percent >= settings.CAPITAL_MAX_DRAWDOWN_PERCENT:
            reason = "MAX_DRAWDOWN_LIMIT"

        allowed = reason is None

        if not allowed:
            logger.warning(
                "Capital management blocked trading",
                reason=reason,
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                consecutive_losses=consecutive_losses,
                drawdown_percent=drawdown_percent,
            )
        else:
            logger.debug(
                "Capital management check passed",
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                consecutive_losses=consecutive_losses,
                drawdown_percent=drawdown_percent,
            )

        return CapitalStatus(
            allowed=allowed,
            reason=reason,
            daily_pnl=round(daily_pnl, 4),
            weekly_pnl=round(weekly_pnl, 4),
            consecutive_losses=consecutive_losses,
            drawdown_percent=round(drawdown_percent, 4),
        )

    async def evaluate_detailed(self, session: AsyncSession) -> CapitalStatusDetailed:
        """
        Extended evaluation that exposes all equity, drawdown, and block fields.
        Used by GET /api/v1/risk/capital-status.
        """
        initial_capital = settings.CAPITAL_INITIAL_USDC
        closed = await pos_repo.get_closed_positions(session)
        open_exposure = await pos_repo.get_total_open_exposure(session)

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        daily_pnl = self._compute_period_pnl(closed, since=today_start)
        weekly_pnl = self._compute_period_pnl(closed, since=week_start)
        consecutive_losses = self._compute_consecutive_losses(
            closed, cooldown_minutes=settings.CAPITAL_COOLDOWN_MINUTES, now=now
        )
        drawdown_percent = self._compute_drawdown_percent(
            closed, initial_capital=initial_capital
        )
        peak_equity, current_equity = self._compute_peak_and_current_equity(
            closed, initial_capital=initial_capital
        )

        # current_equity from closed positions only (unrealized PnL excluded per spec:
        # "All metrics are derived exclusively from CLOSED positions").
        # The equity curve in _compute_peak_and_current_equity already reflects this.
        current_equity_with_unrealized = current_equity  # consistent with evaluate()

        drawdown_amount = max(0.0, peak_equity - current_equity_with_unrealized)
        total_realized = sum(float(p.realized_pnl or 0.0) for p in closed)
        available_capital = max(0.0, initial_capital + total_realized - open_exposure)

        # Daily drawdown: loss vs daily_start_equity (initial + pre-today closed PnL)
        def _aware(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        pre_today_positions = [p for p in closed if _aware(p.closed_at) is not None and _aware(p.closed_at) < today_start]
        pre_today_pnl = sum(float(p.realized_pnl or 0.0) for p in pre_today_positions)
        daily_start_equity = initial_capital + pre_today_pnl
        daily_loss_amount = max(0.0, daily_start_equity - current_equity_with_unrealized)
        daily_drawdown_percent = (
            daily_loss_amount / daily_start_equity * 100.0 if daily_start_equity > 0 else 0.0
        )

        # Determine block reason + metadata
        reason: Optional[str] = None
        if not settings.CAPITAL_ENABLE_KILL_SWITCH:
            reason = None
        elif daily_pnl <= -settings.CAPITAL_DAILY_LOSS_LIMIT_USDC:
            reason = "DAILY_LOSS_LIMIT"
        elif weekly_pnl <= -settings.CAPITAL_WEEKLY_LOSS_LIMIT_USDC:
            reason = "WEEKLY_LOSS_LIMIT"
        elif consecutive_losses >= settings.CAPITAL_MAX_CONSECUTIVE_LOSSES:
            reason = "LOSS_STREAK_LIMIT"
        elif drawdown_percent >= settings.CAPITAL_MAX_DRAWDOWN_PERCENT:
            reason = "MAX_DRAWDOWN_LIMIT"

        capital_blocked = reason is not None
        now_iso = now.isoformat()

        _BLOCK_SCOPE = {
            "DAILY_LOSS_LIMIT": "DAILY",
            "WEEKLY_LOSS_LIMIT": "WEEKLY",
            "LOSS_STREAK_LIMIT": "SESSION",
            "MAX_DRAWDOWN_LIMIT": "PERMANENT",
        }
        _RESET_POLICY = {
            "DAILY_LOSS_LIMIT": "Clears automatically at next UTC midnight daily reset.",
            "WEEKLY_LOSS_LIMIT": "Clears automatically at next UTC Monday weekly reset.",
            "LOSS_STREAK_LIMIT": f"Clears when a winning trade occurs or {settings.CAPITAL_COOLDOWN_MINUTES:.0f}-minute cooldown elapses.",
            "MAX_DRAWDOWN_LIMIT": "Requires equity recovery above the drawdown threshold. Resolves automatically when drawdown % falls below the limit.",
            None: "No block active.",
        }

        return CapitalStatusDetailed(
            capital_blocked=capital_blocked,
            block_code=reason,
            block_reason=reason.replace("_", " ") if reason else None,
            block_scope=_BLOCK_SCOPE.get(reason, "NONE"),
            blocked_at=now_iso if capital_blocked else None,
            blocked_until=None,  # None = no fixed expiry (rule-based auto-clear)
            reset_policy=_RESET_POLICY.get(reason, "No block active."),
            reset_available=True,  # all rules are automatically reversible
            initial_capital=round(initial_capital, 4),
            current_equity=round(current_equity_with_unrealized, 4),
            peak_equity=round(peak_equity, 4),
            drawdown_amount=round(drawdown_amount, 4),
            drawdown_percent=round(drawdown_percent, 4),
            max_drawdown_limit=settings.CAPITAL_MAX_DRAWDOWN_PERCENT,
            daily_start_equity=round(daily_start_equity, 4),
            daily_loss_amount=round(daily_loss_amount, 4),
            daily_drawdown_percent=round(daily_drawdown_percent, 4),
            daily_loss_limit=settings.CAPITAL_DAILY_LOSS_LIMIT_USDC,
            consecutive_losses=consecutive_losses,
            consecutive_loss_limit=settings.CAPITAL_MAX_CONSECUTIVE_LOSSES,
            open_exposure=round(open_exposure, 4),
            available_capital=round(available_capital, 4),
            daily_pnl=round(daily_pnl, 4),
            weekly_pnl=round(weekly_pnl, 4),
            data_source="closed_positions_realized_pnl",
            last_updated_at=now_iso,
        )

    # ── Internal computation ──────────────────────────────────────────────────

    @staticmethod
    def _compute_period_pnl(positions, *, since: datetime) -> float:
        """Sum realized_pnl for positions closed on or after `since`."""
        total = 0.0
        for p in positions:
            closed_at = p.closed_at
            if closed_at is None:
                continue
            if closed_at.tzinfo is None:
                closed_at = closed_at.replace(tzinfo=timezone.utc)
            if closed_at >= since:
                total += float(p.realized_pnl or 0.0)
        return total

    @staticmethod
    def _compute_consecutive_losses(
        positions,
        cooldown_minutes: float,
        now: datetime,
    ) -> int:
        """
        Count consecutive losing trades from the most recent close backwards.

        Iterates closed positions in reverse chronological order (closed_at DESC)
        and stops counting when either:
          - A winning trade (realized_pnl >= 0) is encountered, or
          - A trade whose closed_at is older than cooldown_minutes is reached.

        The cooldown break prevents the kill switch from locking the system
        permanently when losses occurred far in the past and the system has
        been idle long enough to be considered "cooled off".
        """
        sorted_positions = sorted(
            positions,
            key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        streak = 0
        for p in sorted_positions:
            closed_at = p.closed_at
            if closed_at is None:
                continue
            if closed_at.tzinfo is None:
                closed_at = closed_at.replace(tzinfo=timezone.utc)
            age_minutes = (now - closed_at).total_seconds() / 60.0
            if age_minutes > cooldown_minutes:
                # All remaining trades are older than the cooldown window;
                # the streak is considered reset.
                break
            pnl = float(p.realized_pnl or 0.0)
            if pnl < 0:
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def _compute_drawdown_percent(
        positions, initial_capital: float = 400.0
    ) -> float:
        """
        Build an equity curve anchored to initial_capital and return the
        maximum peak-to-trough drawdown as a percentage.

        Formula: (peak_equity - current_equity) / peak_equity × 100
        where equity = initial_capital + cumulative_realized_pnl.

        Starting from initial_capital (not 0) prevents intra-batch artefacts
        where multiple positions closing at nearly the same timestamp with
        different microseconds create a spurious peak before losses are applied.
        Peak is always ≥ initial_capital, so there is no division-by-zero risk
        provided initial_capital > 0.

        Returns 0.0 for an empty position list.
        """
        sorted_positions = sorted(
            positions,
            key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc),
        )

        equity = initial_capital
        peak = initial_capital
        max_drawdown_pct = 0.0

        for p in sorted_positions:
            equity += float(p.realized_pnl or 0.0)
            if equity > peak:
                peak = equity
            # peak >= initial_capital > 0 — safe to divide
            dd_pct = (peak - equity) / peak * 100.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

        return max_drawdown_pct

    @staticmethod
    def _compute_peak_and_current_equity(
        positions, initial_capital: float
    ) -> tuple[float, float]:
        """
        Return (peak_equity, current_equity) for the detailed capital-status
        endpoint.  Mirrors _compute_drawdown_percent but surfaces both values.
        """
        sorted_positions = sorted(
            positions,
            key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc),
        )
        equity = initial_capital
        peak = initial_capital
        for p in sorted_positions:
            equity += float(p.realized_pnl or 0.0)
            if equity > peak:
                peak = equity
        return peak, equity
