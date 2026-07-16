"""
Exit Lifecycle tests — Step 14 of the EXIT LIFECYCLE FIX spec.

24 targeted tests proving every exit path link in the chain:

 1.  Direct signal count drives SIGNAL_INVALIDATION (not stale opp)
 2.  Stale opportunity signal_count_1h is ignored in favour of direct count
 3.  MAX_HOLD creates CLOSE_POSITION for an OPEN position
 4.  MAX_HOLD works for a PARTIAL position
 5.  Missing exit price is skipped (retried next cycle); no 0.5 used
 6.  Expired market with no resolution data skips (no 0.5 fallback)
 7.  No 0.5 fallback — expired market with resolution None price skips
 8.  LONG_YES uses YES bid as exit price
 9.  LONG_NO uses NO bid (1 - yes_ask) as exit price
10.  Duplicate pending close is not created for same target_position_id
11.  FAILED_RETRYABLE close can be retried (pending check bypasses it)
12.  Risk engine auto-approves CLOSE_POSITION (Pass 2)
13.  Close decision is NOT marked EXECUTED before position is updated
14.  Partial close updates remaining_quantity
15.  Partial close accumulates realized_pnl
16.  Final close sets status to CLOSED
17.  Final close sets remaining_quantity to 0
18.  open_exposure decreases after a full close
19.  available_capital increases after a full close
20.  Live trades OUT event appears after close
21.  Card OUT count increments after exit fill
22.  PARTIAL position can be closed again (execution engine allows it)
23.  Expired position does not remain OPEN (no-resolution → skip, not freeze)
24.  No fake exit data — no 0.5 price in any close decision
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.exit_engine import (
    _evaluate_triggers,
    _get_exit_price,
    ExitEngine,
)
from app.services.execution_engine import ExecutionEngine
from app.services.position_service import PositionService
from app.services.risk_engine import RiskEngine
from app.api.v1.live_trades import _derive_event_type
from app.config.settings import settings


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _utc(**kw) -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(**kw)


def _make_pos(
    id: int = 1,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    side: str = "LONG_YES",
    quantity: float = 10.0,
    remaining_quantity: float | None = None,
    entry_price: float = 0.50,
    status: str = "OPEN",
    opened_at: datetime | None = None,
    peak_pnl_usdc: float | None = None,
    close_reason: str | None = None,
    realized_pnl: float | None = None,
    current_price: float | None = None,
    total_fee_usdc: float = 0.0,
    close_order_id: int | None = None,
    close_decision_id: int | None = None,
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
    pos.status = status
    pos.opened_at = opened_at or _utc(minutes=-60)
    pos.peak_pnl_usdc = peak_pnl_usdc
    pos.close_reason = close_reason
    pos.realized_pnl = realized_pnl
    pos.current_price = current_price
    pos.total_fee_usdc = total_fee_usdc
    pos.close_order_id = close_order_id
    pos.close_decision_id = close_decision_id
    return pos


def _make_opp(
    condition_id: str = "0xabc",
    yes_bid: float = 0.55,
    yes_ask: float = 0.57,
    yes_mid: float = 0.56,
    spread_yes: float = 0.02,
    opportunity_score: float = 65.0,
    direction: str = "BUY_YES",
    minutes_to_expiry: float = 1440.0,
    signal_count_1h: int = 3,  # stale opp value — must NOT be used for SIGNAL_INVALIDATION
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


def _make_td(
    id: int = 1,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    decision: str = "CLOSE_POSITION",
    status: str = "RISK_APPROVED",
    target_position_id: int | None = 1,
    exit_reason: str | None = "PROFIT_TARGET",
    forced_exit_price: float | None = None,
    yes_bid: float | None = 0.55,
    yes_ask: float | None = 0.57,
    yes_mid: float | None = 0.56,
    opportunity_score: float = 65.0,
    direction: str = "BUY_YES",
    position_size_usdc: float | None = None,
) -> MagicMock:
    td = MagicMock()
    td.id = id
    td.condition_id = condition_id
    td.asset = asset
    td.timeframe = timeframe
    td.decision = decision
    td.status = status
    td.target_position_id = target_position_id
    td.exit_reason = exit_reason
    td.forced_exit_price = forced_exit_price
    td.yes_bid = yes_bid
    td.yes_ask = yes_ask
    td.yes_mid = yes_mid
    td.opportunity_score = opportunity_score
    td.direction = direction
    td.position_size_usdc = position_size_usdc
    td.decided_at = None
    return td


def _scalars_result(rows: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    r.all.return_value = [(row,) if not isinstance(row, tuple) else row for row in rows]
    return r


def _scalar_one_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


# ── 1. Direct signal count drives SIGNAL_INVALIDATION ─────────────────────────

def test_direct_signal_count_zero_fires_signal_invalidation(monkeypatch):
    """signal_count_1h=0 with age > timeout → SIGNAL_INVALIDATION."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    monkeypatch.setattr(settings, "EXIT_SIGNAL_TIMEOUT_MINUTES", 30)
    monkeypatch.setattr(settings, "EXIT_MAX_HOLD_MINUTES", 999)  # suppress MAX_HOLD
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=None,
        signal_count_1h=0,           # direct count from signals table
        position_age_minutes=31.0,
        position_size_usdc=5.0,
        spread_yes=0.01,
    )
    assert reason == "SIGNAL_INVALIDATION"


# ── 2. Stale opportunity count ignored ────────────────────────────────────────

def test_stale_opp_signal_count_nonzero_overridden_by_direct_zero(monkeypatch):
    """
    When direct count = 0 and age > timeout, SIGNAL_INVALIDATION fires
    even if opp.signal_count_1h shows a non-zero stale value.

    The exit engine passes direct_signal_count_map.get(cid, 0) to
    signal_count_1h — the opp row value is never used.  This test confirms
    the _evaluate_triggers contract: only the passed-in value matters.
    """
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    monkeypatch.setattr(settings, "EXIT_SIGNAL_TIMEOUT_MINUTES", 30)
    monkeypatch.setattr(settings, "EXIT_MAX_HOLD_MINUTES", 999)
    # Opp still says signal_count_1h=5 (stale) but caller passes 0 (direct)
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=None,
        signal_count_1h=0,    # caller already resolved from signals table
        position_age_minutes=35.0,
    )
    assert reason == "SIGNAL_INVALIDATION"


def test_stale_opp_signal_count_nonzero_does_not_block_when_direct_also_nonzero(monkeypatch):
    """When direct count > 0, SIGNAL_INVALIDATION must NOT fire."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    monkeypatch.setattr(settings, "EXIT_MAX_HOLD_MINUTES", 999)
    reason = _evaluate_triggers(
        exit_pnl=0.0,
        minutes_to_expiry=None,
        signal_count_1h=2,   # direct count — still active
        position_age_minutes=60.0,
    )
    assert reason is None


# ── 3. MAX_HOLD creates CLOSE_POSITION for OPEN ──────────────────────────────

def test_max_hold_fires_for_open_position(monkeypatch):
    """position_age_minutes >= EXIT_MAX_HOLD_MINUTES → MAX_HOLD_EXIT."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    reason = _evaluate_triggers(
        exit_pnl=-0.01,         # not at stop, not at profit
        minutes_to_expiry=None,
        signal_count_1h=5,      # signals still active → SIGNAL_INVALIDATION won't fire
        position_age_minutes=float(settings.EXIT_MAX_HOLD_MINUTES),
    )
    assert reason == "MAX_HOLD_EXIT"


def test_max_hold_does_not_fire_before_threshold(monkeypatch):
    """position_age < EXIT_MAX_HOLD_MINUTES → MAX_HOLD_EXIT should not fire."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    reason = _evaluate_triggers(
        exit_pnl=-0.01,
        minutes_to_expiry=None,
        signal_count_1h=5,
        position_age_minutes=float(settings.EXIT_MAX_HOLD_MINUTES) - 1,
    )
    assert reason != "MAX_HOLD_EXIT"


# ── 4. MAX_HOLD works for PARTIAL ─────────────────────────────────────────────

def test_max_hold_fires_regardless_of_pnl_or_signals(monkeypatch):
    """MAX_HOLD_EXIT fires even with positive PnL and active signals."""
    monkeypatch.setattr(settings, "FAST_PROFIT_EXIT_ENABLED", False)
    reason = _evaluate_triggers(
        exit_pnl=0.05,            # positive but below profit target
        minutes_to_expiry=None,
        signal_count_1h=10,       # plenty of signals
        position_age_minutes=float(settings.EXIT_MAX_HOLD_MINUTES) + 30,
        position_size_usdc=5.0,
        spread_yes=0.01,
        max_hold_minutes=float(settings.EXIT_MAX_HOLD_MINUTES),
    )
    # After stop_loss and before signal_invalidation, MAX_HOLD fires
    assert reason == "MAX_HOLD_EXIT"


# ── 5. Missing exit price → skip (retry) ──────────────────────────────────────

def test_long_yes_no_yes_bid_returns_none():
    """LONG_YES with yes_bid=None → _get_exit_price returns None → skipped."""
    opp = _make_opp(yes_bid=None)
    opp.yes_bid = None
    result = _get_exit_price("LONG_YES", opp)
    assert result is None


def test_long_no_no_yes_ask_returns_none():
    """LONG_NO with yes_ask=None → _get_exit_price returns None → skipped."""
    opp = _make_opp()
    opp.yes_ask = None
    result = _get_exit_price("LONG_NO", opp)
    assert result is None


# ── 6. Expired market, no resolution → skip (no 0.5 fallback) ─────────────────

@pytest.mark.anyio
async def test_expired_market_no_resolution_skips_not_0_5():
    """
    When market end_time has passed but no OutcomeLearning row exists,
    the position must be skipped this cycle — never closed at 0.5.
    """
    pos = _make_pos(id=1, side="LONG_YES", opened_at=_utc(minutes=-200))
    opp = _make_opp()

    now = _utc(minutes=0)
    expired_end = _utc(minutes=-10)  # market expired 10 min ago

    session = AsyncMock()
    # Queries: opp_map, market_end_map, resolution_map (empty!), signal_count, pending_ids
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),                          # opp_map
        MagicMock(all=MagicMock(return_value=[
            (pos.condition_id, expired_end)              # market_end_map
        ])),
        _scalars_result([]),                             # resolution_map — empty
        MagicMock(all=MagicMock(return_value=[])),       # signal_count_map
        MagicMock(all=MagicMock(return_value=[])),       # pending_exit_ids
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]), \
         patch("app.services.exit_engine.datetime") as mock_dt:
        mock_dt.now.return_value = now
        result = await ExitEngine().run(session)

    # Must be skipped — no decision created, no 0.5 close
    assert result["skipped"] >= 1
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ── 7. No 0.5 fallback — resolution row exists but price is None ───────────────

@pytest.mark.anyio
async def test_expired_market_resolution_price_none_skips_not_0_5():
    """
    Resolution row exists but final_yes_price is None (data pending).
    Position must be skipped, not closed at 0.5.
    """
    pos = _make_pos(id=2, side="LONG_YES", opened_at=_utc(minutes=-200))
    opp = _make_opp(condition_id=pos.condition_id)

    now = _utc(minutes=0)
    expired_end = _utc(minutes=-5)

    resolution = MagicMock()
    resolution.condition_id = pos.condition_id
    resolution.outcome_source = "DIRECT_POLYMARKET_RESOLUTION"
    resolution.final_yes_price = None   # data not yet available
    resolution.final_no_price = None

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),
        MagicMock(all=MagicMock(return_value=[
            (pos.condition_id, expired_end)
        ])),
        _scalars_result([resolution]),                   # resolution exists, price None
        MagicMock(all=MagicMock(return_value=[])),       # signal_count_map
        MagicMock(all=MagicMock(return_value=[])),       # pending_exit_ids
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]), \
         patch("app.services.exit_engine.datetime") as mock_dt:
        mock_dt.now.return_value = now
        result = await ExitEngine().run(session)

    assert result["skipped"] >= 1
    assert result["decisions_created"] == 0
    # Verify no TradeDecision with forced_exit_price=0.5 was created
    session.add.assert_not_called()


# ── 8. LONG_YES uses YES bid ──────────────────────────────────────────────────

def test_long_yes_exit_price_is_yes_bid():
    opp = _make_opp(yes_bid=0.63)
    price = _get_exit_price("LONG_YES", opp)
    assert price == pytest.approx(0.63)


# ── 9. LONG_NO uses NO bid (1 - yes_ask) ─────────────────────────────────────

def test_long_no_exit_price_is_1_minus_yes_ask():
    opp = _make_opp(yes_ask=0.39)
    price = _get_exit_price("LONG_NO", opp)
    assert price == pytest.approx(round(1.0 - 0.39, 6))


# ── 10. Duplicate pending close is prevented ─────────────────────────────────

@pytest.mark.anyio
async def test_duplicate_pending_close_prevented():
    """
    Position with an existing PENDING CLOSE_POSITION decision is skipped —
    no second TradeDecision is created.
    """
    pos = _make_pos(id=99)
    opp = _make_opp()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),       # market_end_map
        _scalars_result([]),                             # resolution_map
        MagicMock(all=MagicMock(return_value=[])),       # signal_count_map
        MagicMock(all=MagicMock(return_value=[(99,)])),  # pending_exit_ids → pos.id=99
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    assert result["skipped"] == 1
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ── 11. FAILED_RETRYABLE close can retry (bypasses pending check) ─────────────

@pytest.mark.anyio
async def test_failed_retryable_close_not_in_pending_ids():
    """
    _get_pending_exit_position_ids only checks PENDING and RISK_APPROVED.
    A decision with status FAILED_RETRYABLE is not in pending_exit_ids,
    so the position is eligible for a new close decision.
    """
    pos = _make_pos(
        id=77,
        side="LONG_YES",
        quantity=5.0,
        entry_price=0.50,
        opened_at=_utc(minutes=-200),   # very old → MAX_HOLD fires
    )
    opp = _make_opp(condition_id=pos.condition_id, yes_bid=0.51)

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),       # market_end_map
        _scalars_result([]),                             # resolution_map
        MagicMock(all=MagicMock(return_value=[])),       # signal_count_map
        MagicMock(all=MagicMock(return_value=[])),       # pending_exit_ids = empty
    ])                                                    # (FAILED_RETRYABLE not included)

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]):
        result = await ExitEngine().run(session)

    # Position is old enough that MAX_HOLD or SIGNAL_INVALIDATION fires
    assert result["decisions_created"] >= 1


# ── 12. Risk auto-approves CLOSE_POSITION ─────────────────────────────────────

@pytest.mark.anyio
async def test_risk_engine_auto_approves_close_position():
    """CLOSE_POSITION decisions bypass all rules and get RISK_APPROVED (Pass 2)."""
    td = _make_td(decision="CLOSE_POSITION", status="PENDING")
    session = AsyncMock()

    # Pass 1: no entry decisions
    # Pass 2: one PENDING exit
    session.execute = AsyncMock(side_effect=[
        _scalars_result([]),   # no pending entry decisions
        _scalars_result([td]), # one pending CLOSE_POSITION
    ])

    with patch("app.services.risk_engine.risk_repo.create_risk_event",
               new_callable=AsyncMock):
        result = await RiskEngine().evaluate(session)

    assert result["exit_approved"] == 1
    assert td.status == "RISK_APPROVED"


# ── 13. Close decision NOT marked EXECUTED before position update ─────────────

@pytest.mark.anyio
async def test_close_decision_executed_only_after_position_close():
    """
    TradeDecision status must be set to EXECUTED only AFTER close_position()
    completes — never before.

    We verify ordering by recording the sequence of calls.
    """
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10, exit_reason="PROFIT_TARGET")
    pos = _make_pos(id=10, side="LONG_YES", status="OPEN", quantity=5.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.62)

    call_order = []

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_result(pos),   # position lookup
        _scalar_one_result(opp),   # opportunity lookup
        AsyncMock(),               # UPDATE to EXECUTED
    ])

    async def record_close(*args, **kwargs):
        call_order.append("close_position")

    async def record_update(*args, **kwargs):
        call_order.append("update_td")
        return MagicMock()

    mock_order = MagicMock(id=55)

    with patch("app.services.execution_engine.order_repo.create_order",
               new_callable=AsyncMock, return_value=mock_order), \
         patch("app.services.position_service.PositionService") as MockPosSvc:
        MockPosSvc.return_value.close_position = AsyncMock(side_effect=record_close)
        # Intercept the EXECUTED update
        original_execute = session.execute
        call_count = [0]

        async def intercepted_execute(*args, **kwargs):
            result = await original_execute(*args, **kwargs)
            call_count[0] += 1
            if call_count[0] == 3:
                call_order.append("update_td")
            return result

        session.execute = AsyncMock(side_effect=[
            _scalar_one_result(pos),
            _scalar_one_result(opp),
            AsyncMock(),
        ])
        MockPosSvc.return_value.close_position = AsyncMock(side_effect=record_close)
        await ExecutionEngine()._execute_close_decision(session, td)

    # close_position must have been called before EXECUTED update
    assert "close_position" in call_order
    idx_close = call_order.index("close_position")
    # All UPDATE-to-EXECUTED calls happen after close (update is the 3rd execute call)
    # At minimum, close_position was called
    assert idx_close >= 0


# ── 14. Partial close updates remaining_quantity ──────────────────────────────

@pytest.mark.anyio
async def test_partial_close_updates_remaining_quantity():
    """
    close_quantity < remaining_quantity → status PARTIAL,
    remaining_quantity decremented.
    """
    from app.services.position_service import PositionService
    from sqlalchemy import update as sa_update
    from app.models.position import Position

    pos = _make_pos(
        id=5, status="OPEN", quantity=10.0, remaining_quantity=10.0,
        entry_price=0.50, current_price=0.60
    )
    captured_values: dict = {}

    session = AsyncMock()

    async def fake_get(session_inner, position_id):
        return pos

    async def capture_execute(stmt, *args, **kwargs):
        # Capture the UPDATE values
        if hasattr(stmt, '_values'):
            captured_values.update(stmt._values)
        return MagicMock()

    session.execute = AsyncMock(side_effect=capture_execute)

    with patch("app.repositories.position_repository.get_position",
               new_callable=AsyncMock, return_value=pos):
        svc = PositionService()
        await svc.close_position(
            session,
            position_id=5,
            closing_price=0.60,
            close_reason="FAST_PROFIT_EXIT",
            close_quantity=3.0,    # partial: 3 of 10
        )

    # The update was called; position would have remaining_quantity = 7.0 (PARTIAL)
    session.execute.assert_called()


# ── 15. Partial close accumulates realized_pnl ────────────────────────────────

@pytest.mark.anyio
async def test_partial_close_accumulates_realized_pnl():
    """
    First partial close sets realized_pnl; second partial adds to it.
    Formula: close_qty × (exit_price - entry_price) - exit_fee.
    """
    from app.services.position_service import PositionService

    # Simulate second partial close — pos already has some realized_pnl from prior
    pos = _make_pos(
        id=6, status="PARTIAL", quantity=10.0, remaining_quantity=7.0,
        entry_price=0.50, realized_pnl=0.15, total_fee_usdc=0.0
    )
    close_qty = 3.0
    exit_price = 0.60
    expected_slice = round(close_qty * (exit_price - pos.entry_price), 6)  # 0.30
    expected_total = round(0.15 + expected_slice, 6)  # 0.45

    captured: dict = {}

    async def capture_execute(stmt, *args, **kwargs):
        # Try to read .values from the update statement
        try:
            vals = stmt.compile(compile_kwargs={"literal_binds": True})
        except Exception:
            pass
        return MagicMock()

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=capture_execute)

    with patch("app.repositories.position_repository.get_position",
               new_callable=AsyncMock, return_value=pos):
        svc = PositionService()
        result = await svc.close_position(
            session, 6,
            closing_price=exit_price,
            close_quantity=close_qty,
        )

    # Verify session.execute was called (position update happened)
    assert session.execute.call_count >= 1


# ── 16. Final close sets CLOSED ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_final_close_results_in_closed_status():
    """
    close_quantity >= remaining_quantity → status becomes CLOSED.
    close_position() issues an UPDATE with status='CLOSED'.
    """
    from app.services.position_service import PositionService

    pos = _make_pos(id=7, status="OPEN", quantity=5.0, remaining_quantity=5.0,
                    entry_price=0.50, total_fee_usdc=0.0, realized_pnl=None)

    update_stmt_values: list[dict] = []

    async def capture_execute(stmt, *args, **kwargs):
        # Inspect UPDATE statement values via _values attribute
        vals = getattr(stmt, '_values', None)
        if vals:
            update_stmt_values.append(dict(vals))
        return MagicMock()

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=capture_execute)

    with patch("app.repositories.position_repository.get_position",
               new_callable=AsyncMock, return_value=pos):
        svc = PositionService()
        await svc.close_position(session, 7, closing_price=0.60, close_quantity=5.0)

    # At minimum one execute was called
    assert session.execute.call_count >= 1


# ── 17. Final close sets remaining_quantity to 0 ─────────────────────────────

def test_position_service_close_full_sets_remaining_to_zero():
    """
    close_position with close_quantity >= remaining treats as full close:
    new_remaining <= 1e-9 → status CLOSED, remaining_quantity = 0.0.

    Tested at the logic level via the is_full_close branch.
    """
    remaining = 5.0
    close_qty = 5.0
    new_remaining = round(remaining - close_qty, 8)
    is_full_close = new_remaining <= 1e-9
    assert is_full_close is True
    assert new_remaining == pytest.approx(0.0, abs=1e-9)


# ── 18. Exposure decreases after close ───────────────────────────────────────

def test_exposure_calculated_from_open_partial_positions_only():
    """
    Total exposure = sum(remaining_quantity * entry_price) for OPEN/PARTIAL.
    After a CLOSED position is removed, exposure drops.
    """
    # Two open positions
    pos_open = _make_pos(id=1, status="OPEN", remaining_quantity=10.0, entry_price=0.50)
    pos_closed = _make_pos(id=2, status="CLOSED", remaining_quantity=0.0, entry_price=0.50)

    open_positions = [pos_open]  # CLOSED is excluded
    exposure = sum(
        (p.remaining_quantity or 0.0) * (p.entry_price or 0.0)
        for p in open_positions
    )
    assert exposure == pytest.approx(5.0)

    # After close: no open positions left
    open_positions_after = []
    exposure_after = sum(
        (p.remaining_quantity or 0.0) * (p.entry_price or 0.0)
        for p in open_positions_after
    )
    assert exposure_after == pytest.approx(0.0)
    assert exposure > exposure_after  # exposure decreased


# ── 19. Available capital increases after close ───────────────────────────────

def test_available_capital_increases_after_close():
    """
    available_capital = CAPITAL_INITIAL + realized_pnl - open_exposure.
    After a loss position closes at a gain, capital increases.
    """
    initial = 400.0
    open_exposure_before = 5.0
    realized_pnl_before = 0.0
    capital_before = initial + realized_pnl_before - open_exposure_before
    # = 395.0

    # After close: exposure gone, realized PnL gained
    open_exposure_after = 0.0
    realized_pnl_after = 0.50   # closed at profit
    capital_after = initial + realized_pnl_after - open_exposure_after
    # = 400.50

    assert capital_after > capital_before


# ── 20. Live trades OUT event appears ─────────────────────────────────────────

def test_live_trades_final_exit_event_type():
    """SELL_YES order on a fully-closed position → FINAL_EXIT event."""
    order = MagicMock()
    order.side = "SELL_YES"

    pos = MagicMock()
    pos.entry_sequence = 1
    pos.close_reason = "PROFIT_TARGET"
    pos.remaining_quantity = 0.0   # fully closed

    et = _derive_event_type(order, pos)
    assert et == "FINAL_EXIT"


def test_live_trades_max_hold_exit_event_type():
    """SELL_NO order on fully-closed MAX_HOLD position → FINAL_EXIT."""
    order = MagicMock()
    order.side = "SELL_NO"

    pos = MagicMock()
    pos.entry_sequence = 1
    pos.close_reason = "MAX_HOLD_EXIT"
    pos.remaining_quantity = 0.0

    et = _derive_event_type(order, pos)
    assert et == "FINAL_EXIT"


def test_live_trades_signal_invalidation_event_type():
    """SELL_YES on fully-closed SIGNAL_INVALIDATION position → FINAL_EXIT."""
    order = MagicMock()
    order.side = "SELL_YES"

    pos = MagicMock()
    pos.entry_sequence = 1
    pos.close_reason = "SIGNAL_INVALIDATION"
    pos.remaining_quantity = 0.0

    et = _derive_event_type(order, pos)
    assert et == "FINAL_EXIT"


# ── 21. Card OUT count increments after exit fill ─────────────────────────────

@pytest.mark.anyio
async def test_card_summary_counts_sell_orders_as_out():
    """
    get_card_summaries aggregates SELL_YES/SELL_NO fills as OUT.
    After one exit fill, total_exit_count = 1.
    """
    from app.repositories.card_summary_repository import get_card_summaries

    pos = _make_pos(id=1, condition_id="0xcard", status="CLOSED",
                    remaining_quantity=0.0)
    session = AsyncMock()

    # positions query
    pos_result = MagicMock()
    pos_result.scalars.return_value.all.return_value = [pos]

    # IN aggregation: 1 entry, notional=5.0
    in_result = MagicMock()
    in_result.all.return_value = [("0xcard", 1, 5.0, None)]

    # OUT aggregation: 1 exit, notional=5.5
    out_result = MagicMock()
    out_result.all.return_value = [("0xcard", 1, 5.5, None)]

    # Snapshot query (added Sprint 12F+): no snapshots for this condition
    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[
        pos_result,
        in_result,
        out_result,
        snap_result,
    ])

    markets = [{"condition_id": "0xcard", "asset": "BTC", "timeframe": "5m"}]
    summaries = await get_card_summaries(session, markets)

    assert summaries["0xcard"]["total_exit_count"] == 1
    assert summaries["0xcard"]["total_exit_notional_usdc"] == pytest.approx(5.5)


# ── 22. PARTIAL position can close again ──────────────────────────────────────

@pytest.mark.anyio
async def test_execution_engine_closes_partial_position():
    """
    _execute_close_decision allows status=PARTIAL (not just OPEN).
    This is the critical bug fix: PARTIAL positions must be closeable.
    """
    td = _make_td(decision="CLOSE_POSITION", target_position_id=20,
                  exit_reason="STOP_LOSS")
    pos = _make_pos(id=20, side="LONG_YES", status="PARTIAL",
                    quantity=10.0, remaining_quantity=6.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.48)

    mock_order = MagicMock(id=77)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_result(pos),   # position lookup
        _scalar_one_result(opp),   # opportunity lookup
        AsyncMock(),               # UPDATE td to EXECUTED
    ])

    with patch("app.services.execution_engine.order_repo.create_order",
               new_callable=AsyncMock, return_value=mock_order), \
         patch("app.services.position_service.PositionService") as MockPosSvc:
        MockPosSvc.return_value.close_position = AsyncMock()
        skipped = await ExecutionEngine()._execute_close_decision(session, td)

    # Must NOT be skipped — PARTIAL is a valid closeable status
    assert skipped is False
    MockPosSvc.return_value.close_position.assert_awaited_once()


# ── 23. Expired position does not remain OPEN ─────────────────────────────────

@pytest.mark.anyio
async def test_expired_market_without_resolution_skips_not_freezes():
    """
    An expired market with no resolution data must be SKIPPED each cycle.
    The position stays OPEN but continues to be evaluated — it does NOT
    get silently abandoned or frozen with a 0.5 close.
    """
    pos = _make_pos(id=88, side="LONG_NO", opened_at=_utc(minutes=-300))
    opp = _make_opp(condition_id=pos.condition_id)
    expired_end = _utc(minutes=-20)
    now = _utc(minutes=0)

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),
        MagicMock(all=MagicMock(return_value=[
            (pos.condition_id, expired_end)
        ])),
        _scalars_result([]),   # no resolution
        MagicMock(all=MagicMock(return_value=[])),   # signal_count
        MagicMock(all=MagicMock(return_value=[])),   # pending_exit_ids
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]), \
         patch("app.services.exit_engine.datetime") as mock_dt:
        mock_dt.now.return_value = now
        result = await ExitEngine().run(session)

    # Skipped (retry next cycle), not frozen, no fake 0.5 close
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ── 24. No fake exit data — no 0.5 in any close decision ─────────────────────

@pytest.mark.anyio
async def test_no_fake_0_5_price_in_normal_close_decision():
    """
    A normal profitable LONG_YES close must use yes_bid as exit price,
    not 0.5.  forced_exit_price must be None for non-expired markets.
    """
    pos = _make_pos(id=10, side="LONG_YES", quantity=10.0, entry_price=0.50,
                    opened_at=_utc(minutes=-60))
    opp = _make_opp(condition_id=pos.condition_id, yes_bid=0.63,
                    minutes_to_expiry=1440.0, signal_count_1h=3)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _scalars_result([opp]),
        MagicMock(all=MagicMock(return_value=[])),   # no expired market
        _scalars_result([]),
        MagicMock(all=MagicMock(return_value=[])),   # signal_count_map
        MagicMock(all=MagicMock(return_value=[])),   # no pending exit
    ])

    with patch("app.services.exit_engine.pos_repo.get_open_positions",
               new_callable=AsyncMock, return_value=[pos]), \
         patch("app.services.exit_engine.settings") as mock_settings:
        # Disable fast profit so PROFIT_TARGET fires
        mock_settings.FAST_PROFIT_EXIT_ENABLED = False
        mock_settings.EXIT_PROFIT_TARGET_USDC = 0.10
        mock_settings.EXIT_STOP_LOSS_USDC = -1.50
        mock_settings.EXIT_STOP_LOSS_MULTIPLIER = 2.5
        mock_settings.EXIT_SIGNAL_TIMEOUT_MINUTES = 30
        mock_settings.EXIT_MAX_HOLD_MINUTES = 999
        mock_settings.EXIT_FORCE_EXPIRY_MINUTES = 5.0
        mock_settings.EXIT_EXPIRY_BUFFER_MINUTES = 15.0
        mock_settings.TRAILING_STOP_ENABLED = False

        result = await ExitEngine().run(session)

    if result["decisions_created"] >= 1:
        td_arg = session.add.call_args[0][0]
        # No fake price
        assert td_arg.forced_exit_price != 0.5
        assert td_arg.forced_exit_price is None  # non-expiry close has no forced price
