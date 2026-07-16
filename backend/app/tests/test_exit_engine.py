"""
Exit Engine tests — Layer 11 + Phase 4 (Parts A & E).

Covers:
  - _position_age_minutes(): 2 pure-function cases
  - _get_exit_price(): 5 pure-function cases
  - _compute_dynamic_stop_loss(): 2 pure-function cases (Phase 4 Part A)
  - _evaluate_triggers(): 12 pure-function cases (all triggers + dynamic stop + trailing stop)
  - ExitEngine.run(): 7 integration cases with mocked repos/session
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.exit_engine import (
    _position_age_minutes,
    _get_exit_price,
    _compute_dynamic_stop_loss,
    _evaluate_triggers,
    ExitEngine,
)
from app.config.settings import settings


# ── Helpers ───────────────────────────────────────────────────────────────────


def _utc(**kwargs) -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(**kwargs)


def _make_pos(
    id: int = 1,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    side: str = "LONG_YES",
    quantity: float = 10.0,
    entry_price: float = 0.50,
    opened_at: datetime | None = None,
    peak_pnl_usdc: float | None = None,
    remaining_quantity: float | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.id = id
    pos.condition_id = condition_id
    pos.asset = asset
    pos.timeframe = timeframe
    pos.side = side
    pos.quantity = quantity
    pos.remaining_quantity = remaining_quantity if remaining_quantity is not None else quantity
    pos.entry_price = entry_price
    pos.opened_at = opened_at or _utc(minutes=-60)
    pos.peak_pnl_usdc = peak_pnl_usdc
    return pos


def _make_opp(
    condition_id: str = "0xabc",
    yes_bid: float = 0.60,
    yes_ask: float = 0.61,
    yes_mid: float = 0.605,
    spread_yes: float = 0.01,
    opportunity_score: float = 70.0,
    direction: str = "BUY_YES",
    minutes_to_expiry: float = 1440.0,
    signal_count_1h: int = 3,
) -> MagicMock:
    opp = MagicMock()
    opp.condition_id = condition_id
    opp.yes_bid = yes_bid
    opp.yes_ask = yes_ask
    opp.yes_mid = yes_mid
    opp.spread_yes = spread_yes
    opp.opportunity_score = opportunity_score
    opp.direction = direction
    opp.minutes_to_expiry = minutes_to_expiry
    opp.signal_count_1h = signal_count_1h
    return opp


def _make_exec_result(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    # Also support .all() directly (for position-ID query)
    result.all.return_value = [(r,) if not isinstance(r, tuple) else r for r in rows]
    return result


# ── _position_age_minutes ─────────────────────────────────────────────────────


def test_position_age_minutes_tz_aware():
    now = _utc(minutes=90)
    opened_at = _utc(minutes=0)
    assert _position_age_minutes(opened_at, now) == pytest.approx(90.0)


def test_position_age_minutes_tz_naive_handled():
    """tz-naive opened_at is treated as UTC without raising."""
    now = _utc(minutes=30)
    opened_at = datetime(2026, 1, 1, 12, 0, 0)  # no tzinfo
    assert _position_age_minutes(opened_at, now) == pytest.approx(30.0)


# ── _get_exit_price ───────────────────────────────────────────────────────────


def test_get_exit_price_long_yes_returns_yes_bid():
    opp = _make_opp(yes_bid=0.62)
    assert _get_exit_price("LONG_YES", opp) == pytest.approx(0.62)


def test_get_exit_price_long_no_returns_1_minus_yes_ask():
    opp = _make_opp(yes_ask=0.40)
    result = _get_exit_price("LONG_NO", opp)
    assert result == pytest.approx(round(1.0 - 0.40, 6))


def test_get_exit_price_long_no_yes_ask_none_returns_none():
    opp = _make_opp()
    opp.yes_ask = None
    assert _get_exit_price("LONG_NO", opp) is None


def test_get_exit_price_opp_none_returns_none():
    assert _get_exit_price("LONG_YES", None) is None


def test_get_exit_price_unknown_side_returns_none():
    opp = _make_opp()
    assert _get_exit_price("UNKNOWN_SIDE", opp) is None


# ── _compute_dynamic_stop_loss ────────────────────────────────────────────────


def test_compute_dynamic_stop_loss_basic():
    """SpreadCost = 10 × 0.01 = 0.10; StopLoss = 0.10 × 2.5 = 0.25 → threshold = -0.25."""
    threshold = _compute_dynamic_stop_loss(
        position_size_usdc=10.0, spread_yes=0.01, multiplier=2.5
    )
    assert threshold == pytest.approx(-0.25)


def test_compute_dynamic_stop_loss_larger_position():
    """Position $50, spread 0.02, multiplier 2.0 → SpreadCost=$1.00, threshold=-$2.00."""
    threshold = _compute_dynamic_stop_loss(
        position_size_usdc=50.0, spread_yes=0.02, multiplier=2.0
    )
    assert threshold == pytest.approx(-2.0)


# ── _evaluate_triggers ────────────────────────────────────────────────────────


def test_evaluate_trigger_expiry_exit_hard():
    """minutes_to_expiry < EXIT_FORCE_EXPIRY_MINUTES always fires, regardless of PnL."""
    reason = _evaluate_triggers(
        exit_pnl=-5.0,
        minutes_to_expiry=settings.EXIT_FORCE_EXPIRY_MINUTES - 0.1,
        signal_count_1h=10,
        position_age_minutes=1.0,
    )
    assert reason == "EXPIRY_EXIT"


def test_evaluate_trigger_expiry_exit_soft_fires_when_profitable():
    """Buffer window fires only when exit_pnl > 0."""
    reason = _evaluate_triggers(
        exit_pnl=0.01,
        minutes_to_expiry=settings.EXIT_EXPIRY_BUFFER_MINUTES - 0.1,
        signal_count_1h=10,
        position_age_minutes=1.0,
    )
    assert reason == "EXPIRY_EXIT"


def test_evaluate_trigger_expiry_exit_soft_does_not_fire_when_losing():
    """Buffer window is NOT triggered when exit_pnl <= 0."""
    reason = _evaluate_triggers(
        exit_pnl=-0.01,
        minutes_to_expiry=settings.EXIT_EXPIRY_BUFFER_MINUTES - 0.1,
        signal_count_1h=10,
        position_age_minutes=1.0,
    )
    assert reason != "EXPIRY_EXIT"


def test_evaluate_trigger_stop_loss():
    """Static fallback fires when no spread data supplied."""
    reason = _evaluate_triggers(
        exit_pnl=settings.EXIT_STOP_LOSS_USDC,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
    )
    assert reason == "STOP_LOSS"


def test_evaluate_trigger_stop_loss_dynamic_fires():
    """Dynamic stop loss fires when exit_pnl ≤ -(position_size × spread × multiplier)."""
    # position_size=10, spread=0.01, multiplier=2.5 → threshold=-0.25
    reason = _evaluate_triggers(
        exit_pnl=-0.25,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason == "STOP_LOSS"


def test_evaluate_trigger_stop_loss_dynamic_no_fire_above_threshold():
    """Dynamic stop: exit_pnl above threshold does not trigger stop loss."""
    # threshold = -(10 × 0.01 × 2.5) = -0.25; pnl = -0.20 → no fire
    reason = _evaluate_triggers(
        exit_pnl=-0.20,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason is None


def test_evaluate_trigger_stop_loss_static_floor_protects_large_position():
    """
    When dynamic threshold is more negative than static floor, the static floor wins.

    Large position + thin spread: dynamic = -(100 × 0.01 × 2.5) = -2.50.
    Static floor = -1.50.  max(-1.50, -2.50) = -1.50 → floor takes over.
    exit_pnl = -1.60 <= -1.50 → STOP_LOSS fires via the floor, not the dynamic threshold.
    """
    reason = _evaluate_triggers(
        exit_pnl=-1.60,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=100.0,
        spread_yes=0.01,
    )
    assert reason == "STOP_LOSS"


def test_evaluate_trigger_stop_loss_dynamic_tighter_than_floor():
    """
    When dynamic is tighter (less negative) than the floor, dynamic wins.

    Small position: dynamic = -(5 × 0.01 × 2.5) = -0.125.
    Static floor = -1.50.  max(-1.50, -0.125) = -0.125 → dynamic wins.
    exit_pnl = -0.20 < -0.125 → STOP_LOSS fires via dynamic threshold.
    exit_pnl = -0.10 > -0.125 → no trigger.
    """
    # Should fire: -0.20 <= -0.125
    reason_fires = _evaluate_triggers(
        exit_pnl=-0.20,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=5.0,
        spread_yes=0.01,
    )
    assert reason_fires == "STOP_LOSS"

    # Should NOT fire: -0.10 > -0.125
    reason_no_fire = _evaluate_triggers(
        exit_pnl=-0.10,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=5.0,
        spread_yes=0.01,
    )
    assert reason_no_fire is None


def test_evaluate_trigger_profit_target(monkeypatch):
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    reason = _evaluate_triggers(
        exit_pnl=settings.EXIT_PROFIT_TARGET_USDC,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
    )
    assert reason == "PROFIT_TARGET"


def test_evaluate_trigger_trailing_stop_fires(monkeypatch):
    """Trailing stop fires when peak > 0 and exit_pnl < peak - trailing_threshold."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    monkeypatch.setattr(settings, "TRAILING_STOP_ENABLED", True)
    monkeypatch.setattr(settings, "TRAILING_STOP_DISTANCE", 0.02)
    # position_size=10, distance=0.02 → trailing_drawdown_threshold=0.20
    # peak=0.50; fires when exit_pnl < 0.50-0.20=0.30
    # exit_pnl=0.05 is below PROFIT_TARGET (0.10) so PROFIT_TARGET doesn't fire first
    reason = _evaluate_triggers(
        exit_pnl=0.05,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=10.0,
        peak_pnl_usdc=0.50,
    )
    assert reason == "TRAILING_STOP"


def test_evaluate_trigger_trailing_stop_disabled_by_default(monkeypatch):
    """Trailing stop does NOT fire when TRAILING_STOP_ENABLED is False (default)."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    reason = _evaluate_triggers(
        exit_pnl=0.05,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=10.0,
        peak_pnl_usdc=0.50,
    )
    # Default TRAILING_STOP_ENABLED=False → no trailing stop; fast exit disabled above
    assert reason is None


def test_evaluate_trigger_trailing_stop_not_armed_when_peak_not_profitable(monkeypatch):
    """Trailing stop requires peak_pnl > 0 to arm (avoids triggering on losses)."""
    monkeypatch.setattr(settings, "TRAILING_STOP_ENABLED", True)
    monkeypatch.setattr(settings, "TRAILING_STOP_DISTANCE", 0.02)
    reason = _evaluate_triggers(
        exit_pnl=-0.05,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=10.0,
        position_size_usdc=10.0,
        peak_pnl_usdc=-0.01,  # was never profitable → trailing stop not armed
    )
    assert reason is None


def test_evaluate_trigger_signal_invalidation():
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=None,
        signal_count_1h=0,
        position_age_minutes=settings.EXIT_SIGNAL_TIMEOUT_MINUTES + 1,
    )
    assert reason == "SIGNAL_INVALIDATION"


def test_evaluate_trigger_signal_invalidation_not_fired_when_signals_present():
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=None,
        signal_count_1h=1,
        position_age_minutes=settings.EXIT_SIGNAL_TIMEOUT_MINUTES + 1,
    )
    assert reason is None


def test_evaluate_trigger_no_trigger_returns_none():
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=1440.0,
        signal_count_1h=5,
        position_age_minutes=5.0,
    )
    assert reason is None


# ── ExitEngine.run() ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_run_no_open_positions_returns_zero_summary():
    session = AsyncMock()

    with patch(
        "app.services.exit_engine.pos_repo.get_open_positions",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await ExitEngine().run(session)

    assert result == {
        "evaluated": 0,
        "decisions_created": 0,
        "skipped": 0,
        "errors": 0,
        "duration_ms": 0,
    }


@pytest.mark.anyio
async def test_run_position_with_pending_exit_is_skipped():
    pos = _make_pos(id=42)
    session = AsyncMock()
    # opp query returns one opp, market end_time query, resolution query,
    # pending-exit-ids query returns {42}
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([_make_opp()]),  # opp_map query
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[])),  # direct signal count map (new)
        MagicMock(all=MagicMock(return_value=[(42,)])),  # pending exit IDs
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["evaluated"] == 1
    assert result["skipped"] == 1
    assert result["decisions_created"] == 0


@pytest.mark.anyio
async def test_run_position_no_exit_price_is_skipped():
    """LONG_NO with yes_ask=None → no executable price → skipped."""
    pos = _make_pos(id=1, side="LONG_NO")
    opp = _make_opp()
    opp.yes_ask = None  # forces _get_exit_price → None
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[])),  # direct signal count map (new)
        MagicMock(all=MagicMock(return_value=[])),  # pending exit IDs
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["skipped"] == 1
    assert result["decisions_created"] == 0


@pytest.mark.anyio
async def test_run_profit_target_creates_close_position(monkeypatch):
    # quantity=10, entry=0.50, yes_bid=0.62 → exit_pnl = 10 * (0.62 - 0.50) = 1.2 > 0.10
    # Disable FAST_PROFIT_EXIT so PROFIT_TARGET triggers first (as this test intends)
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    pos = _make_pos(id=1, side="LONG_YES", quantity=10.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.62, minutes_to_expiry=1440.0, signal_count_1h=3)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[])),  # direct signal count map (new)
        MagicMock(all=MagicMock(return_value=[])),  # pending exit IDs
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["decisions_created"] == 1
    assert result["skipped"] == 0
    session.add.assert_called_once()
    td_arg = session.add.call_args[0][0]
    assert td_arg.decision == "CLOSE_POSITION"
    assert td_arg.exit_reason == "PROFIT_TARGET"
    assert td_arg.target_position_id == 1
    assert td_arg.forced_exit_price is None


@pytest.mark.anyio
async def test_run_stop_loss_creates_close_position():
    # quantity=100, entry=0.50, yes_bid=0.484 → exit_pnl = 100 * (0.484 - 0.50) = -1.60
    # spread_yes=0.01, position_size=100*0.50=50, dynamic_threshold=-(50*0.01*2.5)=-1.25
    # -1.60 <= -1.25 → STOP_LOSS
    pos = _make_pos(id=2, side="LONG_YES", quantity=100.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.484, minutes_to_expiry=1440.0, signal_count_1h=3, spread_yes=0.01)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[])),  # direct signal count map (new)
        MagicMock(all=MagicMock(return_value=[])),  # pending exit IDs
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["decisions_created"] == 1
    td_arg = session.add.call_args[0][0]
    assert td_arg.exit_reason == "STOP_LOSS"
    assert td_arg.forced_exit_price is None


@pytest.mark.anyio
async def test_run_no_trigger_no_decision(monkeypatch):
    """Position within all limits and profitable but not at target — no close emitted."""
    # PnL = 1 * (0.509 - 0.50) = 0.009 < 0.10 PROFIT_TARGET
    # dynamic stop: position_size=0.50, spread=0.01, threshold=-(0.50*0.01*2.5)=-0.0125
    # pnl=0.009 > -0.0125 → stop not hit
    # MAX_HOLD suppressed: set to 999999 so the mock position (opened_at is in the past
    # relative to real datetime.now()) doesn't trigger it.
    monkeypatch.setattr(settings, "EXIT_MAX_HOLD_MINUTES", 999999)
    monkeypatch.setattr(settings, "EXIT_SIGNAL_TIMEOUT_MINUTES", 999999)
    pos = _make_pos(id=3, side="LONG_YES", quantity=1.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.509, minutes_to_expiry=1440.0, signal_count_1h=3, spread_yes=0.01)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[("0xabc", 3)])),  # direct signal count map — 3 active signals
        MagicMock(all=MagicMock(return_value=[])),  # pending exit IDs
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["decisions_created"] == 0
    assert result["skipped"] == 0
    session.add.assert_not_called()


@pytest.mark.anyio
async def test_run_exception_counted_as_error():
    """An exception during position processing is caught and counted as error."""
    pos = _make_pos(id=1, side="LONG_YES", quantity=10.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.62)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),  # market end_time map
        _make_exec_result([]),  # resolution map
        MagicMock(all=MagicMock(return_value=[])),  # direct signal count map (new)
        MagicMock(all=MagicMock(return_value=[])),  # pending exit IDs
    ])
    # session.add is synchronous in SQLAlchemy; use MagicMock so side_effect raises immediately
    session.add = MagicMock(side_effect=RuntimeError("db constraint"))

    with patch("app.services.exit_engine.pos_repo.get_open_positions", new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["errors"] == 1
    assert result["decisions_created"] == 0


# ── FAST_PROFIT_EXIT trigger (Phase 12L) ─────────────────────────────────────
#
# Tests the new Priority 3 fast-profit exit that fires before PROFIT_TARGET
# when net PnL clears the bar and hold time is satisfied.


def test_fast_profit_exit_fires_after_hold_time(monkeypatch):
    """FAST_PROFIT_EXIT triggers when: hold met, spread OK, net PnL positive."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 0.05)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.03)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "MAX_ACCEPTABLE_EXIT_SPREAD", 0.05)
    # hold = 5 min (300s >= 2s); gross_pnl = 0.07 >= 0.05; net = 0.06 >= 0.03
    reason = _evaluate_triggers(
        exit_pnl=0.07,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=5.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason == "FAST_PROFIT_EXIT"


def test_fast_profit_exit_blocked_before_minimum_hold(monkeypatch):
    """FAST_PROFIT_EXIT does NOT fire before MIN_POSITION_HOLD_SECONDS."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 60)  # 60s hold required
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 0.05)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.03)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "MAX_ACCEPTABLE_EXIT_SPREAD", 0.05)
    # hold = 0.5 min (30s < 60s) → gate not met
    reason = _evaluate_triggers(
        exit_pnl=0.07,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=0.5,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason != "FAST_PROFIT_EXIT"


def test_fast_profit_exit_blocked_when_net_profit_too_low(monkeypatch):
    """Gross profit above threshold but net after costs too low → no fast exit."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 0.05)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.05)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.04)
    monkeypatch.setattr(settings, "MAX_ACCEPTABLE_EXIT_SPREAD", 0.05)
    # gross = 0.07, estimated_cost = 0.04 → net = 0.03 < 0.05 → BLOCK
    reason = _evaluate_triggers(
        exit_pnl=0.07,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=5.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason != "FAST_PROFIT_EXIT"


def test_fast_profit_exit_blocked_when_spread_too_high(monkeypatch):
    """Wide spread (> MAX_ACCEPTABLE_EXIT_SPREAD) blocks fast exit."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 0.05)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.03)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "MAX_ACCEPTABLE_EXIT_SPREAD", 0.03)
    # spread = 0.10 > 0.03 → acceptable_spread = False → no fast exit
    reason = _evaluate_triggers(
        exit_pnl=0.07,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=5.0,
        position_size_usdc=10.0,
        spread_yes=0.10,
    )
    assert reason != "FAST_PROFIT_EXIT"


def test_fast_profit_exit_disabled_when_setting_off(monkeypatch):
    """FAST_PROFIT_EXIT does not fire when FAST_PROFIT_EXIT_ENABLED=False."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 0.05)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.03)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "EXIT_PROFIT_TARGET_USDC", 0.50)  # push standard target high
    reason = _evaluate_triggers(
        exit_pnl=0.07,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=5.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason is None


def test_fast_profit_exit_fires_on_percent_target(monkeypatch):
    """FAST_PROFIT_EXIT triggers when % profit >= FAST_PROFIT_TARGET_PERCENT."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    # Keep USD target high so percent path is the trigger
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_USDC", 999.0)
    monkeypatch.setattr(settings, "FAST_PROFIT_TARGET_PERCENT", 0.5)
    monkeypatch.setattr(settings, "MIN_NET_PROFIT_AFTER_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "ESTIMATED_EXIT_COST_USDC", 0.01)
    monkeypatch.setattr(settings, "MAX_ACCEPTABLE_EXIT_SPREAD", 0.05)
    # position_size=10, gross_pnl=0.06 → 0.6% > 0.5% → percent_target_met=True
    reason = _evaluate_triggers(
        exit_pnl=0.06,
        minutes_to_expiry=1440.0,
        signal_count_1h=3,
        position_age_minutes=5.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason == "FAST_PROFIT_EXIT"


def test_fast_profit_exit_priority_lower_than_stop_loss(monkeypatch):
    """STOP_LOSS always fires before FAST_PROFIT_EXIT (negative PnL cannot trigger fast exit)."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    monkeypatch.setattr(settings, "MIN_POSITION_HOLD_SECONDS", 2)
    # exit_pnl is negative → cannot satisfy net_pnl >= MIN_NET_PROFIT threshold
    reason = _evaluate_triggers(
        exit_pnl=-1.60,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=5.0,
        position_size_usdc=100.0,
        spread_yes=0.01,
    )
    assert reason == "STOP_LOSS"  # stop fires before fast exit is even evaluated


def test_expiry_fallback_still_works_with_fast_exit_enabled(monkeypatch):
    """EXPIRY_EXIT (Priority 1) still fires before FAST_PROFIT_EXIT."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", True)
    reason = _evaluate_triggers(
        exit_pnl=0.50,   # very profitable
        minutes_to_expiry=settings.EXIT_FORCE_EXPIRY_MINUTES - 0.1,
        signal_count_1h=3,
        position_age_minutes=60.0,
        position_size_usdc=10.0,
        spread_yes=0.01,
    )
    assert reason == "EXPIRY_EXIT"
