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
        consecutive_losses = self._compute_consecutive_losses(closed)
        drawdown_percent = self._compute_drawdown_percent(closed)

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
    def _compute_consecutive_losses(positions) -> int:
        """
        Count consecutive losing trades from the most recent close backwards.

        Iterates closed positions in reverse chronological order (closed_at DESC)
        and stops counting when the first winning trade (realized_pnl > 0) is found.
        """
        sorted_positions = sorted(
            positions,
            key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        streak = 0
        for p in sorted_positions:
            pnl = float(p.realized_pnl or 0.0)
            if pnl < 0:
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def _compute_drawdown_percent(positions) -> float:
        """
        Build an equity curve (cumulative realized PnL ordered by closed_at ASC)
        and return the maximum peak-to-trough drawdown as a percentage.

        Formula: (peak_equity - current_equity) / peak_equity * 100
        Returns 0.0 when peak_equity <= 0 (no gains ever recorded).
        """
        sorted_positions = sorted(
            positions,
            key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc),
        )

        equity = 0.0
        peak = 0.0
        max_drawdown_pct = 0.0

        for p in sorted_positions:
            equity += float(p.realized_pnl or 0.0)
            if equity > peak:
                peak = equity
            if peak > 0:
                dd_pct = (peak - equity) / peak * 100.0
                if dd_pct > max_drawdown_pct:
                    max_drawdown_pct = dd_pct

        return max_drawdown_pct
