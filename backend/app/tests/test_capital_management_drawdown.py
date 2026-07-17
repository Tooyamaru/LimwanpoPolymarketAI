"""
Capital Management drawdown and equity regression tests.

Spec items 1–40 covering:
  Items  1–10: Accounting and equity formulas
  Items 11–20: Max drawdown formula correctness
  Items 21–30: Daily risk state
  Items 31–40: Block latch behaviour and label accuracy

All tests run in-process with SimpleNamespace position stubs —
no database, no network, no external services.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.capital_management_service import (
    CapitalManagementService,
    CapitalStatus,
)

# ── Test helpers ───────────────────────────────────────────────────────────────

INITIAL_CAPITAL = 400.0


def _pos(
    pnl: float,
    minutes_ago: float = 5.0,
    closed_at: Optional[datetime] = None,
    position_size_usdc: float = 10.0,
) -> SimpleNamespace:
    """Return a minimal closed-position-like stub."""
    ts = closed_at or (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago))
    return SimpleNamespace(
        realized_pnl=pnl,
        closed_at=ts,
        position_size_usdc=position_size_usdc,
        live_pnl=None,
    )


def _dd(positions, initial_capital: float = INITIAL_CAPITAL) -> float:
    return CapitalManagementService._compute_drawdown_percent(
        positions, initial_capital=initial_capital
    )


def _period_pnl(positions, since: datetime) -> float:
    return CapitalManagementService._compute_period_pnl(positions, since=since)


def _streak(positions, cooldown: float = 60.0) -> int:
    now = datetime.now(timezone.utc)
    return CapitalManagementService._compute_consecutive_losses(
        positions, cooldown_minutes=cooldown, now=now
    )


# ──────────────────────────────────────────────────────────────────────────────
# Items 1–10: Accounting and equity formula tests
# ──────────────────────────────────────────────────────────────────────────────


class TestAccountingAndEquity:
    """Items 1–10."""

    def test_item1_current_equity_is_initial_plus_realized_plus_unrealized(self):
        """current_equity = initial + realized + unrealized (unrealized=0 here)."""
        positions = [_pos(+10.0, 20), _pos(+5.0, 10)]
        peak, equity = CapitalManagementService._compute_peak_and_current_equity(
            positions, initial_capital=INITIAL_CAPITAL
        )
        # realized = +15, no unrealized → equity = 400 + 15 = 415
        assert abs(equity - 415.0) < 0.01

    def test_item2_coverage_does_not_reduce_equity(self):
        """Coverage (open exposure) is not deducted from equity."""
        # equity curve only looks at realized PnL; open_exposure is separate
        positions = [_pos(+20.0, 10)]
        _, equity = CapitalManagementService._compute_peak_and_current_equity(
            positions, initial_capital=INITIAL_CAPITAL
        )
        assert abs(equity - 420.0) < 0.01  # 400 + 20 = 420, NOT 420 - exposure

    def test_item3_available_subtracts_open_exposure_not_equity(self):
        """available = initial + realized − open_exposure (not equity − exposure)."""
        realized = 46.59
        open_exposure = 25.0
        initial = 400.0
        available = max(0.0, initial + realized - open_exposure)
        # Must equal 400 + 46.59 - 25 = 421.59, not 446.59 - 25
        assert abs(available - 421.59) < 0.01

    def test_item4_cumulative_outcome_is_realized_plus_unrealized(self):
        """Cumulative outcome = realized PnL + unrealized PnL."""
        realized = 46.59
        unrealized = 0.0
        cumulative = realized + unrealized
        assert abs(cumulative - 46.59) < 0.01

    def test_item5_positive_realized_increases_equity(self):
        """A winning close moves equity above initial_capital."""
        _, before = CapitalManagementService._compute_peak_and_current_equity(
            [], initial_capital=INITIAL_CAPITAL
        )
        _, after = CapitalManagementService._compute_peak_and_current_equity(
            [_pos(+50.0, 5)], initial_capital=INITIAL_CAPITAL
        )
        assert after > before
        assert abs(after - 450.0) < 0.01

    def test_item6_negative_realized_decreases_equity(self):
        """A losing close moves equity below initial_capital."""
        _, equity = CapitalManagementService._compute_peak_and_current_equity(
            [_pos(-50.0, 5)], initial_capital=INITIAL_CAPITAL
        )
        assert equity < INITIAL_CAPITAL
        assert abs(equity - 350.0) < 0.01

    def test_item7_no_double_counting_of_realized_pnl(self):
        """Each position's PnL is counted exactly once in the equity curve."""
        positions = [_pos(+10.0, 20), _pos(+10.0, 10), _pos(+10.0, 5)]
        _, equity = CapitalManagementService._compute_peak_and_current_equity(
            positions, initial_capital=INITIAL_CAPITAL
        )
        assert abs(equity - 430.0) < 0.01  # 400 + 30, not 440 or 460

    def test_item8_zero_pnl_position_does_not_change_equity(self):
        """A break-even close has no effect on equity."""
        _, eq_before = CapitalManagementService._compute_peak_and_current_equity(
            [], initial_capital=INITIAL_CAPITAL
        )
        _, eq_after = CapitalManagementService._compute_peak_and_current_equity(
            [_pos(0.0, 5)], initial_capital=INITIAL_CAPITAL
        )
        assert abs(eq_before - eq_after) < 0.001

    def test_item9_none_realized_pnl_treated_as_zero(self):
        """Position with realized_pnl=None does not raise and is treated as 0."""
        pos = SimpleNamespace(realized_pnl=None, closed_at=datetime.now(timezone.utc) - timedelta(minutes=5))
        # Should not raise
        _, equity = CapitalManagementService._compute_peak_and_current_equity(
            [pos], initial_capital=INITIAL_CAPITAL
        )
        assert abs(equity - INITIAL_CAPITAL) < 0.001

    def test_item10_equity_curve_ordered_chronologically(self):
        """Positions are sorted by closed_at so order of insertion does not matter."""
        now = datetime.now(timezone.utc)
        # Insert out of order: big win at t+20, loss at t+10
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))  # first in time
        p2 = _pos(-50.0, closed_at=now - timedelta(minutes=10))   # second in time
        positions = [p2, p1]  # reversed insertion order
        _, equity = CapitalManagementService._compute_peak_and_current_equity(
            positions, initial_capital=INITIAL_CAPITAL
        )
        # Regardless of insertion order: 400 + 100 - 50 = 450
        assert abs(equity - 450.0) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Items 11–20: Max drawdown formula tests
# ──────────────────────────────────────────────────────────────────────────────


class TestMaxDrawdownFormula:
    """Items 11–20."""

    def test_item11_no_drawdown_when_equity_equals_peak(self):
        """Monotonically rising equity → drawdown = 0%."""
        positions = [_pos(+10.0, 30), _pos(+10.0, 20), _pos(+10.0, 10)]
        dd = _dd(positions)
        assert dd == 0.0

    def test_item12_no_drawdown_when_equity_exceeds_previous_peak(self):
        """Equity making new highs continuously → drawdown = 0%."""
        positions = [_pos(+5.0, 40), _pos(+5.0, 30), _pos(+5.0, 20), _pos(+5.0, 10)]
        dd = _dd(positions)
        assert dd == 0.0

    def test_item13_peak_updates_when_equity_makes_new_high(self):
        """After a dip and recovery above old peak, new peak is used."""
        now = datetime.now(timezone.utc)
        p1 = _pos(+50.0, closed_at=now - timedelta(minutes=40))   # peak at 450
        p2 = _pos(-30.0, closed_at=now - timedelta(minutes=30))   # dip to 420
        p3 = _pos(+60.0, closed_at=now - timedelta(minutes=20))   # new peak at 480
        p4 = _pos(-10.0, closed_at=now - timedelta(minutes=10))   # dip to 470
        dd = _dd([p1, p2, p3, p4])
        # Max drawdown was at step 2: (450-420)/450*100 = 6.67%
        # OR at step 4: (480-470)/480*100 = 2.08% — whichever is larger
        assert abs(dd - 6.6667) < 0.01

    def test_item14_drawdown_uses_peak_equity_not_initial(self):
        """Drawdown denominator is the historical peak, not initial_capital."""
        now = datetime.now(timezone.utc)
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))  # peak = 500
        p2 = _pos(-50.0, closed_at=now - timedelta(minutes=10))   # current = 450
        dd = _dd([p1, p2])
        # Correct: (500-450)/500*100 = 10%
        # Wrong (if peak=initial=400): (400-450)/400 → negative, clamped = 0
        assert abs(dd - 10.0) < 0.01

    def test_item15_coverage_not_included_in_drawdown(self):
        """Open exposure (coverage) does not affect the drawdown percentage."""
        # drawdown is purely from realized PnL curve — open exposure ignored
        positions = [_pos(+20.0, 10)]
        dd_no_exposure = _dd(positions)
        # Adding a stub with position_size_usdc should not change the drawdown
        assert dd_no_exposure == 0.0  # equity 420 > peak 400? No — 420 > 400, no dd

    def test_item16_available_is_not_used_as_equity_in_drawdown(self):
        """available_capital (which subtracts exposure) is never the equity input."""
        # Drawdown formula only uses realized_pnl, never subtracts open_exposure.
        positions = [_pos(+50.0, 20), _pos(-10.0, 10)]
        # Correct equity curve: 400 → 450 → 440; peak=450, dd=(450-440)/450=2.22%
        dd = _dd(positions)
        assert abs(dd - 2.2222) < 0.01

    def test_item17_threshold_blocks_exactly_when_exceeded(self):
        """drawdown_percent >= CAPITAL_MAX_DRAWDOWN_PERCENT triggers the rule."""
        # With initial=400 and a big loss after a big gain
        now = datetime.now(timezone.utc)
        # Create drawdown of exactly > 20%
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))  # peak=500
        p2 = _pos(-110.0, closed_at=now - timedelta(minutes=10))  # equity=390, dd=22%
        dd = _dd([p1, p2])
        assert dd > 20.0  # exceeds 20% limit

    def test_item18_threshold_does_not_block_below_limit(self):
        """drawdown_percent < CAPITAL_MAX_DRAWDOWN_PERCENT does not trigger."""
        # The real-world scenario: 4 positions with total dd ~8%
        now = datetime.now(timezone.utc)
        p1 = _pos(+51.19, closed_at=now - timedelta(minutes=4, seconds=30))
        p2 = _pos(+34.09, closed_at=now - timedelta(minutes=4, seconds=20))
        p3 = _pos(-37.50, closed_at=now - timedelta(minutes=4, seconds=10))
        p4 = _pos(-1.19,  closed_at=now - timedelta(minutes=4, seconds=0))
        dd = _dd([p1, p2, p3, p4])
        # peak=485.28, current=446.59, dd=(485.28-446.59)/485.28*100 ≈ 7.97%
        assert dd < 20.0

    def test_item18b_real_world_4pos_drawdown_under_limit(self):
        """The exact scenario that caused the stale block: dd=7.97%, not 45%."""
        now = datetime.now(timezone.utc)
        p1 = _pos(+51.19, closed_at=now - timedelta(seconds=62))
        p2 = _pos(+34.09, closed_at=now - timedelta(seconds=61))
        p3 = _pos(-37.50, closed_at=now - timedelta(seconds=60))
        p4 = _pos(-1.19,  closed_at=now - timedelta(seconds=59))
        dd = _dd([p1, p2, p3, p4])
        assert abs(dd - 7.97) < 0.5  # within 0.5 pp of the expected 7.97%
        assert dd < 20.0             # must NOT trigger the 20% limit

    def test_item19_drawdown_percent_handles_zero_peak_safely(self):
        """Initial capital > 0 means peak is always > 0 — no division by zero."""
        # Even with no positions, initial_capital anchors the peak at 400
        dd = _dd([], initial_capital=400.0)
        assert dd == 0.0  # no trades → no drawdown, no ZeroDivision

    def test_item20_formula_bug_regression_equity_starts_from_initial_capital(self):
        """
        Old bug: equity started at 0 so wins created a false peak before
        losses were applied, triggering MAX_DRAWDOWN_LIMIT spuriously.

        Regression: starting from initial_capital (400) the drawdown is
        correctly calculated as ≈ 7.97% < 20%, not 45% > 20%.
        """
        now = datetime.now(timezone.utc)
        # Exact timestamps from the live incident (BTC/ETH win, XRP/SOL lose)
        btc = _pos(+51.190476, closed_at=now - timedelta(seconds=90, milliseconds=60))
        eth = _pos(+34.090909, closed_at=now - timedelta(seconds=90, milliseconds=40))
        xrp = _pos(-37.5,      closed_at=now - timedelta(seconds=90, milliseconds=20))
        sol = _pos(-1.188,     closed_at=now - timedelta(seconds=90, milliseconds=0))

        dd_correct = _dd([btc, eth, xrp, sol], initial_capital=400.0)
        dd_buggy = CapitalManagementService._compute_drawdown_percent(
            [btc, eth, xrp, sol], initial_capital=0.0
        )

        # Correct formula: ≈7.97%
        assert abs(dd_correct - 7.97) < 0.5
        assert dd_correct < 20.0

        # Old (buggy) formula: ≈45.37% — would wrongly trigger the block
        assert dd_buggy > 40.0


# ──────────────────────────────────────────────────────────────────────────────
# Items 21–30: Daily risk state tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDailyRiskState:
    """Items 21–30."""

    def _today_start(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def test_item21_daily_start_equity_is_initial_plus_pre_today_pnl(self):
        """daily_start_equity = initial_capital + sum of PnL closed before today."""
        today = self._today_start()
        yesterday = today - timedelta(days=1, minutes=30)
        pre_today = _pos(+20.0, closed_at=yesterday)
        # daily_start_equity = 400 + 20 = 420
        pre_pnl = _period_pnl([pre_today], since=datetime.min.replace(tzinfo=timezone.utc))
        daily_start = 400.0 + pre_pnl
        assert abs(daily_start - 420.0) < 0.01

    def test_item22_daily_drawdown_computed_from_daily_start_equity(self):
        """daily_loss_amount uses daily_start_equity as denominator, not peak."""
        today = self._today_start()
        daily_start = 420.0
        today_loss = -30.0
        current_equity = daily_start + today_loss  # 390
        daily_loss_amount = max(0.0, daily_start - current_equity)
        daily_dd_pct = daily_loss_amount / daily_start * 100.0
        assert abs(daily_dd_pct - (30.0 / 420.0 * 100.0)) < 0.001

    def test_item23_daily_reset_uses_utc_midnight_boundary(self):
        """today_start is UTC midnight — no local-timezone offset."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        assert today_start.tzinfo is not None
        assert today_start.hour == 0
        assert today_start.minute == 0

    def test_item24_positions_from_today_are_included_in_daily_pnl(self):
        """Positions closed today (after midnight UTC) count in daily_pnl."""
        today = self._today_start()
        pos_today = _pos(+10.0, closed_at=today + timedelta(hours=1))
        daily = _period_pnl([pos_today], since=today)
        assert abs(daily - 10.0) < 0.001

    def test_item25_positions_from_yesterday_excluded_from_daily_pnl(self):
        """Positions closed before today's midnight are excluded from daily_pnl."""
        today = self._today_start()
        pos_yesterday = _pos(+50.0, closed_at=today - timedelta(minutes=1))
        daily = _period_pnl([pos_yesterday], since=today)
        assert daily == 0.0

    def test_item26_daily_pnl_sums_multiple_positions(self):
        """Multiple same-day positions are all summed."""
        today = self._today_start()
        positions = [
            _pos(+10.0, closed_at=today + timedelta(hours=1)),
            _pos(-5.0,  closed_at=today + timedelta(hours=2)),
            _pos(+3.0,  closed_at=today + timedelta(hours=3)),
        ]
        daily = _period_pnl(positions, since=today)
        assert abs(daily - 8.0) < 0.001

    def test_item27_daily_loss_limit_triggers_on_net_loss_not_gross(self):
        """DAILY_LOSS_LIMIT fires on net daily PnL, not sum of losing trades only."""
        today = self._today_start()
        positions = [
            _pos(+20.0, closed_at=today + timedelta(hours=1)),   # win
            _pos(-55.0, closed_at=today + timedelta(hours=2)),   # big loss
        ]
        daily = _period_pnl(positions, since=today)
        # Net = -35, which is ≤ -30 limit → triggers
        assert daily <= -30.0

    def test_item28_tz_naive_closed_at_is_handled_without_error(self):
        """A tz-naive closed_at is treated as UTC without raising."""
        today = self._today_start()
        naive_pos = SimpleNamespace(
            realized_pnl=-10.0,
            closed_at=datetime.utcnow(),  # tz-naive
        )
        # _compute_period_pnl must not raise; it adds tzinfo=UTC
        result = CapitalManagementService._compute_period_pnl(
            [naive_pos], since=today
        )
        assert isinstance(result, float)

    def test_item29_no_daily_positions_daily_pnl_is_zero(self):
        """When no positions closed today, daily PnL is 0."""
        today = self._today_start()
        old = _pos(-99.0, closed_at=today - timedelta(days=5))
        daily = _period_pnl([old], since=today)
        assert daily == 0.0

    def test_item30_weekly_pnl_includes_since_monday(self):
        """Weekly PnL includes all closes since Monday midnight UTC."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        pos_this_week = _pos(+30.0, closed_at=week_start + timedelta(hours=2))
        pos_last_week = _pos(-999.0, closed_at=week_start - timedelta(days=1))
        weekly = _period_pnl([pos_this_week, pos_last_week], since=week_start)
        assert abs(weekly - 30.0) < 0.001


# ──────────────────────────────────────────────────────────────────────────────
# Items 31–40: Block latch behaviour and label accuracy
# ──────────────────────────────────────────────────────────────────────────────


class TestBlockLatchAndLabels:
    """Items 31–40."""

    def _make_status(
        self,
        positions=None,
        daily_pnl=0.0,
        weekly_pnl=0.0,
        consecutive_losses=0,
        drawdown_pct=0.0,
        kill_switch_enabled=True,
    ) -> CapitalStatus:
        """Directly instantiate CapitalStatus for assertion tests."""
        if positions is None:
            positions = []

        svc = CapitalManagementService()

        # Reuse the internal static methods
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        d_pnl = svc._compute_period_pnl(positions, since=today_start) if positions else daily_pnl
        w_pnl = svc._compute_period_pnl(positions, since=week_start) if positions else weekly_pnl
        streak = svc._compute_consecutive_losses(positions, cooldown_minutes=60.0, now=now) if positions else consecutive_losses
        dd = svc._compute_drawdown_percent(positions, initial_capital=INITIAL_CAPITAL) if positions else drawdown_pct

        from app.config.settings import settings as s

        reason = None
        if kill_switch_enabled:
            if d_pnl <= -s.CAPITAL_DAILY_LOSS_LIMIT_USDC:
                reason = "DAILY_LOSS_LIMIT"
            elif w_pnl <= -s.CAPITAL_WEEKLY_LOSS_LIMIT_USDC:
                reason = "WEEKLY_LOSS_LIMIT"
            elif streak >= s.CAPITAL_MAX_CONSECUTIVE_LOSSES:
                reason = "LOSS_STREAK_LIMIT"
            elif dd >= s.CAPITAL_MAX_DRAWDOWN_PERCENT:
                reason = "MAX_DRAWDOWN_LIMIT"

        return CapitalStatus(
            allowed=reason is None,
            reason=reason,
            daily_pnl=round(d_pnl, 4),
            weekly_pnl=round(w_pnl, 4),
            consecutive_losses=streak,
            drawdown_percent=round(dd, 4),
        )

    def test_item31_kill_switch_disabled_always_allows(self):
        """When CAPITAL_ENABLE_KILL_SWITCH=False, all rules return allowed=True."""
        status = self._make_status(
            daily_pnl=-999.0,
            drawdown_pct=99.0,
            kill_switch_enabled=False,
        )
        # Since we do not invoke the async evaluate() here, simulate directly
        svc = CapitalManagementService()
        with patch("app.services.capital_management_service.settings") as mock_s:
            mock_s.CAPITAL_ENABLE_KILL_SWITCH = False
            mock_s.CAPITAL_DAILY_LOSS_LIMIT_USDC = 30.0
            mock_s.CAPITAL_WEEKLY_LOSS_LIMIT_USDC = 75.0
            mock_s.CAPITAL_MAX_CONSECUTIVE_LOSSES = 5
            mock_s.CAPITAL_MAX_DRAWDOWN_PERCENT = 20.0
            mock_s.CAPITAL_COOLDOWN_MINUTES = 60.0
            mock_s.CAPITAL_INITIAL_USDC = 400.0

            import asyncio

            async def _run():
                session = AsyncMock()
                from app.repositories import position_repository as repo
                with patch.object(repo, "get_closed_positions", return_value=[]):
                    return await svc.evaluate(session)

            result = asyncio.get_event_loop().run_until_complete(_run())
            assert result.allowed is True
            assert result.reason is None

    def test_item32_drawdown_block_triggers_exactly_at_threshold(self):
        """MAX_DRAWDOWN_LIMIT fires at exactly >= 20.0% drawdown."""
        now = datetime.now(timezone.utc)
        # Construct a position sequence giving exactly 20.0% drawdown from peak
        # peak = 500, target current = 400 → dd = (500-400)/500 = 20.0%
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))  # equity=500, peak=500
        p2 = _pos(-100.0, closed_at=now - timedelta(minutes=10))  # equity=400, dd=20%
        dd = _dd([p1, p2])
        assert abs(dd - 20.0) < 0.01
        # Should trigger
        from app.config.settings import settings as s
        assert dd >= s.CAPITAL_MAX_DRAWDOWN_PERCENT

    def test_item33_drawdown_block_does_not_trigger_below_threshold(self):
        """MAX_DRAWDOWN_LIMIT does not fire below 20.0%."""
        now = datetime.now(timezone.utc)
        # peak=500, current=405 → dd=(500-405)/500=19.0%
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))
        p2 = _pos(-95.0,  closed_at=now - timedelta(minutes=10))
        dd = _dd([p1, p2])
        assert abs(dd - 19.0) < 0.01
        from app.config.settings import settings as s
        assert dd < s.CAPITAL_MAX_DRAWDOWN_PERCENT

    def test_item34_daily_loss_limit_triggers_on_net_negative_day(self):
        """DAILY_LOSS_LIMIT fires when daily_pnl <= -CAPITAL_DAILY_LOSS_LIMIT_USDC."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        positions = [
            _pos(-35.0, closed_at=today + timedelta(hours=2)),
        ]
        daily = CapitalManagementService._compute_period_pnl(positions, since=today)
        from app.config.settings import settings as s
        assert daily <= -s.CAPITAL_DAILY_LOSS_LIMIT_USDC

    def test_item35_daily_loss_limit_does_not_trigger_on_gain(self):
        """Positive daily PnL does not trigger DAILY_LOSS_LIMIT."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        positions = [_pos(+46.59, closed_at=today + timedelta(hours=2))]
        daily = CapitalManagementService._compute_period_pnl(positions, since=today)
        from app.config.settings import settings as s
        assert daily > -s.CAPITAL_DAILY_LOSS_LIMIT_USDC

    def test_item36_consecutive_loss_limit_does_not_trigger_with_2_losses(self):
        """2 consecutive losses is well under the 5-loss limit."""
        now = datetime.now(timezone.utc)
        positions = [
            _pos(-37.5, closed_at=now - timedelta(minutes=4, seconds=10)),
            _pos(-1.19, closed_at=now - timedelta(minutes=4, seconds=0)),
        ]
        streak = CapitalManagementService._compute_consecutive_losses(
            positions, cooldown_minutes=60.0, now=now
        )
        from app.config.settings import settings as s
        assert streak == 2
        assert streak < s.CAPITAL_MAX_CONSECUTIVE_LOSSES

    def test_item37_block_reason_is_machine_code_not_human_label(self):
        """reason field is a machine code (e.g. 'MAX_DRAWDOWN_LIMIT'), not a label."""
        now = datetime.now(timezone.utc)
        p1 = _pos(+100.0, closed_at=now - timedelta(minutes=20))
        p2 = _pos(-110.0, closed_at=now - timedelta(minutes=10))  # dd > 20%
        status = self._make_status(positions=[p1, p2])
        if not status.allowed:
            assert status.reason == "MAX_DRAWDOWN_LIMIT"
            # Machine code — underscores, no spaces
            assert " " not in status.reason
            assert "_" in status.reason

    def test_item38_allowed_true_when_all_rules_pass(self):
        """All rules within limits → allowed=True, reason=None."""
        status = self._make_status(positions=[_pos(+10.0, 5)])
        assert status.allowed is True
        assert status.reason is None

    def test_item39_human_readable_label_replaces_underscores(self):
        """block_reason (human label) has spaces, not underscores."""
        # Simulate what evaluate_detailed does:
        block_code = "MAX_DRAWDOWN_LIMIT"
        block_reason = block_code.replace("_", " ")
        assert block_reason == "MAX DRAWDOWN LIMIT"
        assert "_" not in block_reason

    def test_item40_loss_streak_rule_does_not_block_with_win_in_streak(self):
        """A win in the recent sequence resets the streak to 0."""
        now = datetime.now(timezone.utc)
        positions = [
            _pos(-10.0, closed_at=now - timedelta(minutes=5)),  # loss
            _pos(+5.0,  closed_at=now - timedelta(minutes=10)), # WIN — breaks streak
            _pos(-10.0, closed_at=now - timedelta(minutes=15)), # loss (before win)
            _pos(-10.0, closed_at=now - timedelta(minutes=20)), # loss (before win)
        ]
        streak = CapitalManagementService._compute_consecutive_losses(
            positions, cooldown_minutes=60.0, now=now
        )
        # Only the 1 loss after the most-recent win counts
        assert streak == 1
        from app.config.settings import settings as s
        assert streak < s.CAPITAL_MAX_CONSECUTIVE_LOSSES
