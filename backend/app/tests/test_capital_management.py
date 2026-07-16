"""
Capital Management Service tests — Layer 16.

Focuses on the consecutive-loss streak counter and cooldown reset behaviour.
Uses SimpleNamespace to construct minimal position-like objects so the tests
run without a database.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.capital_management_service import CapitalManagementService


# ── helpers ────────────────────────────────────────────────────────────────────

def _pos(pnl: float, minutes_ago: float) -> SimpleNamespace:
    """Return a minimal position-like object with closed_at and realized_pnl."""
    closed_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return SimpleNamespace(realized_pnl=pnl, closed_at=closed_at)


def _streak(positions, cooldown: float = 60.0) -> int:
    now = datetime.now(timezone.utc)
    return CapitalManagementService._compute_consecutive_losses(
        positions, cooldown_minutes=cooldown, now=now
    )


# ── _compute_consecutive_losses ────────────────────────────────────────────────

class TestComputeConsecutiveLosses:

    def test_no_positions_returns_zero(self):
        assert _streak([]) == 0

    def test_single_recent_loss_counts(self):
        assert _streak([_pos(-0.50, 5)]) == 1

    def test_single_recent_win_returns_zero(self):
        assert _streak([_pos(+0.10, 5)]) == 0

    def test_multiple_recent_losses_all_counted(self):
        positions = [
            _pos(-0.50, 5),
            _pos(-0.50, 10),
            _pos(-0.50, 15),
        ]
        assert _streak(positions) == 3

    def test_win_breaks_streak_immediately(self):
        # Loss → Win → Loss: only the first loss counts
        positions = [
            _pos(-0.50, 5),   # most recent — loss → streak = 1
            _pos(+0.10, 10),  # win          → stop counting
            _pos(-0.50, 15),  # loss before win — not counted
        ]
        assert _streak(positions) == 1

    def test_all_old_losses_beyond_cooldown_reset_to_zero(self):
        positions = [
            _pos(-0.50, 90),   # 90 min ago — beyond 60 min cooldown
            _pos(-0.50, 120),  # 120 min ago — also beyond
        ]
        assert _streak(positions) == 0

    def test_mixed_recent_and_old_counts_only_recent(self):
        # Two recent losses, then an old one beyond the cooldown
        positions = [
            _pos(-0.50, 5),   # recent
            _pos(-0.50, 10),  # recent
            _pos(-0.50, 90),  # old — cooldown break stops count here
        ]
        assert _streak(positions) == 2

    def test_exactly_at_cooldown_boundary_is_included(self):
        # Trade closed 59 min ago — within 60 min window
        assert _streak([_pos(-0.50, 59)], cooldown=60.0) == 1

    def test_just_over_cooldown_boundary_resets(self):
        # Trade closed 61 min ago — beyond 60 min window
        assert _streak([_pos(-0.50, 61)], cooldown=60.0) == 0

    def test_five_recent_losses_trigger_threshold(self):
        positions = [_pos(-0.50, i * 2) for i in range(1, 6)]
        assert _streak(positions) == 5

    def test_cooldown_resets_after_idle_period(self):
        # Simulates the deadlock scenario: 12 old consecutive losses that
        # happened > 60 min ago.  The streak must read as 0 after cooldown.
        positions = [_pos(-0.50, 70 + i) for i in range(12)]
        assert _streak(positions) == 0

    def test_tz_naive_closed_at_handled_gracefully(self):
        # closed_at without tzinfo should not raise; streak still computed
        pos = SimpleNamespace(
            realized_pnl=-0.50,
            closed_at=datetime.utcnow() - timedelta(minutes=5),  # tz-naive
        )
        result = _streak([pos])
        assert result == 1

    def test_none_closed_at_is_skipped(self):
        pos = SimpleNamespace(realized_pnl=-0.50, closed_at=None)
        assert _streak([pos]) == 0
