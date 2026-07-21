"""
Execution Engine tests — Layer 7 (Paper Mode).

Covers:
  - ExecutionEngine.run(): 5 integration cases (no-ops, filled, skipped, exit, error)
  - ExecutionEngine._execute_decision(): 5 cases (YES/NO paths, missing price, quantity)
  - ExecutionEngine._execute_close_decision(): 6 cases (guards + LONG_YES/NO success)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.execution_engine import ExecutionEngine


# ── Binding constants (module-level so market + td share identical values) ────
# Window is WINDOW_LIVE: START = now-60s, END = START+300s = now+240s.
# 240 s of future buffer prevents the window from expiring mid-test-run.
_NOW_REF = datetime.now(timezone.utc)
_BINDING_SLUG = "btc-updown-5m-1784271300"
_BINDING_START = _NOW_REF - timedelta(seconds=60)
_BINDING_END = _BINDING_START + timedelta(seconds=300)   # = _NOW_REF + 240s


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_active_market(condition_id: str = "0xabc") -> MagicMock:
    """Return a mock MarketUniverse row with a valid WINDOW_LIVE prediction window."""
    market = MagicMock()
    market.condition_id = condition_id
    market.event_slug = _BINDING_SLUG
    market.prediction_window_start = _BINDING_START
    market.prediction_window_end = _BINDING_END
    # Keep contract times consistent (not used by new gate, but harmless)
    market.start_time = _BINDING_START
    market.end_time = _BINDING_END
    return market


def _make_td(
    id: int = 1,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    decision: str = "OPEN_LONG_YES",
    status: str = "RISK_APPROVED",
    yes_ask: float | None = 0.57,
    yes_bid: float | None = 0.53,
    yes_mid: float | None = 0.55,
    spread_yes: float | None = 0.04,
    opportunity_score: float = 75.0,
    direction: str = "BUY_YES",
    position_size_usdc: float | None = 10.0,
    exit_reason: str | None = None,
    target_position_id: int | None = None,
    forced_exit_price: float | None = None,
    decision_event_slug: str | None = _BINDING_SLUG,
    decision_prediction_window_start: datetime | None = _BINDING_START,
    decision_prediction_window_end: datetime | None = _BINDING_END,
) -> MagicMock:
    td = MagicMock()
    td.id = id
    td.condition_id = condition_id
    td.asset = asset
    td.timeframe = timeframe
    td.decision = decision
    td.status = status
    td.yes_ask = yes_ask
    td.yes_bid = yes_bid
    td.yes_mid = yes_mid
    td.spread_yes = spread_yes
    td.opportunity_score = opportunity_score
    td.direction = direction
    td.position_size_usdc = position_size_usdc
    td.exit_reason = exit_reason
    td.target_position_id = target_position_id
    # Phase 10: defaults to None like the real ORM column; only forced-expiry
    # CLOSE_POSITION decisions set this.
    td.forced_exit_price = forced_exit_price
    # Set to None so the stale-decision check (decided_at is not None) is skipped
    td.decided_at = None
    # Phase A: window binding fields
    td.decision_event_slug = decision_event_slug
    td.decision_prediction_window_start = decision_prediction_window_start
    td.decision_prediction_window_end = decision_prediction_window_end
    return td


def _make_pos(
    id: int = 10,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    side: str = "LONG_YES",
    status: str = "OPEN",
    quantity: float = 20.0,
    entry_price: float = 0.50,
    remaining_quantity: float | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.id = id
    pos.condition_id = condition_id
    pos.asset = asset
    pos.timeframe = timeframe
    pos.side = side
    pos.status = status
    pos.quantity = quantity
    pos.remaining_quantity = remaining_quantity if remaining_quantity is not None else quantity
    pos.entry_price = entry_price
    return pos


def _make_opp(
    yes_bid: float = 0.60,
    yes_ask: float = 0.62,
) -> MagicMock:
    opp = MagicMock()
    opp.yes_bid = yes_bid
    opp.yes_ask = yes_ask
    return opp


def _make_exec_result_scalars(rows: list) -> MagicMock:
    """Fake result for result.scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _make_exec_result_scalar_one_or_none(value) -> MagicMock:
    """Fake result for result.scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ── ExecutionEngine.run() ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_run_no_decisions_returns_zero_summary():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalars([]),  # no entry decisions
        _make_exec_result_scalars([]),  # no exit decisions
    ])

    result = await ExecutionEngine().run(session)

    assert result["decisions_processed"] == 0
    assert result["orders_filled"] == 0
    assert result["orders_skipped"] == 0
    assert result["exits_closed"] == 0
    assert result["exits_skipped"] == 0
    assert result["errors"] == 0


@pytest.mark.anyio
async def test_run_entry_decision_filled():
    td = _make_td(decision="OPEN_LONG_YES")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalars([td]),
        _make_exec_result_scalars([]),
    ])

    mock_order = MagicMock()
    with patch.object(ExecutionEngine, "_execute_decision", new_callable=AsyncMock, return_value=(mock_order, False)):
        result = await ExecutionEngine().run(session)

    assert result["decisions_processed"] == 1
    assert result["orders_filled"] == 1
    assert result["orders_skipped"] == 0


@pytest.mark.anyio
async def test_run_entry_decision_skipped_when_price_missing():
    td = _make_td(decision="OPEN_LONG_YES")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalars([td]),
        _make_exec_result_scalars([]),
    ])

    with patch.object(ExecutionEngine, "_execute_decision", new_callable=AsyncMock, return_value=(None, True)):
        result = await ExecutionEngine().run(session)

    assert result["orders_skipped"] == 1
    assert result["orders_filled"] == 0


@pytest.mark.anyio
async def test_run_exit_decision_closed():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalars([]),  # no entry
        _make_exec_result_scalars([td]),
    ])

    with patch.object(ExecutionEngine, "_execute_close_decision", new_callable=AsyncMock, return_value=False):
        result = await ExecutionEngine().run(session)

    assert result["exits_closed"] == 1
    assert result["exits_skipped"] == 0


@pytest.mark.anyio
async def test_run_entry_exception_counted_as_error():
    td = _make_td()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalars([td]),
        _make_exec_result_scalars([]),
    ])

    with patch.object(ExecutionEngine, "_execute_decision", new_callable=AsyncMock, side_effect=RuntimeError("crash")):
        result = await ExecutionEngine().run(session)

    assert result["errors"] == 1
    assert result["orders_filled"] == 0


# ── ExecutionEngine._execute_decision() ───────────────────────────────────────


@pytest.mark.anyio
async def test_execute_decision_long_yes_fills_at_yes_ask():
    td = _make_td(decision="OPEN_LONG_YES", yes_ask=0.60, position_size_usdc=12.0)
    active_mkt = _make_active_market()
    session = AsyncMock()
    # Call 1: market lifecycle lookup; Call 2: UPDATE trade_decision to EXECUTED
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(active_mkt),
        AsyncMock(),
    ])
    mock_order = MagicMock()

    with (
        patch("app.services.execution_engine.order_repo.create_order", new_callable=AsyncMock, return_value=mock_order),
    ):
        order, skipped = await ExecutionEngine()._execute_decision(session, td)

    assert skipped is False
    assert order is mock_order
    # Two session.execute calls: market lookup + EXECUTED status update
    assert session.execute.await_count == 2


@pytest.mark.anyio
async def test_execute_decision_long_no_fills_at_one_minus_yes_bid():
    td = _make_td(decision="OPEN_LONG_NO", yes_bid=0.40, position_size_usdc=10.0)
    active_mkt = _make_active_market()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(active_mkt),
        AsyncMock(),
    ])
    mock_order = MagicMock()

    with patch("app.services.execution_engine.order_repo.create_order", new_callable=AsyncMock, return_value=mock_order):
        order, skipped = await ExecutionEngine()._execute_decision(session, td)

    assert skipped is False
    assert order is mock_order


@pytest.mark.anyio
async def test_execute_decision_long_yes_skips_when_yes_ask_none():
    td = _make_td(decision="OPEN_LONG_YES", yes_ask=None)
    active_mkt = _make_active_market()
    session = AsyncMock()
    # Only the market lookup is called; no UPDATE when price is missing
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(active_mkt),
    ])

    order, skipped = await ExecutionEngine()._execute_decision(session, td)

    assert skipped is True
    assert order is None
    # Only the market-lookup execute was called; no EXECUTED update
    assert session.execute.await_count == 1


@pytest.mark.anyio
async def test_execute_decision_long_no_skips_when_yes_bid_none():
    td = _make_td(decision="OPEN_LONG_NO", yes_bid=None)
    active_mkt = _make_active_market()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(active_mkt),
    ])

    order, skipped = await ExecutionEngine()._execute_decision(session, td)

    assert skipped is True
    assert order is None
    assert session.execute.await_count == 1


@pytest.mark.anyio
async def test_execute_decision_quantity_computed_from_position_size():
    """quantity = position_size_usdc / fill_price (rounded to 6dp)."""
    td = _make_td(decision="OPEN_LONG_YES", yes_ask=0.50, position_size_usdc=10.0)
    # Expected quantity: 10.0 / 0.50 = 20.0
    active_mkt = _make_active_market()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(active_mkt),
        AsyncMock(),
    ])
    captured = {}

    async def capture_order(session, **kwargs):
        captured.update(kwargs)
        return MagicMock(id=99)

    with patch("app.services.execution_engine.order_repo.create_order", side_effect=capture_order):
        await ExecutionEngine()._execute_decision(session, td)

    assert captured["quantity"] == pytest.approx(20.0)
    assert captured["side"] == "LONG_YES"


# ── ExecutionEngine._execute_close_decision() ─────────────────────────────────


@pytest.mark.anyio
async def test_execute_close_decision_no_target_id_is_skipped():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=None)
    session = AsyncMock()

    result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is True  # skipped
    # td marked EXECUTED via UPDATE
    session.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_execute_close_decision_position_not_found_is_skipped():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=99)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(None),  # pos query → not found
        AsyncMock(),  # UPDATE to EXECUTED
    ])

    result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is True


@pytest.mark.anyio
async def test_execute_close_decision_already_closed_position_is_skipped():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10)
    pos = _make_pos(id=10, status="CLOSED")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(pos),  # pos query
        AsyncMock(),  # UPDATE to EXECUTED
    ])

    result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is True


@pytest.mark.anyio
async def test_execute_close_decision_long_yes_no_yes_bid_is_skipped():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10)
    pos = _make_pos(id=10, side="LONG_YES", status="OPEN")
    opp = _make_opp(yes_bid=None)
    opp.yes_bid = None
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(pos),  # pos query
        _make_exec_result_scalar_one_or_none(opp),  # opp query
    ])

    result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is True


@pytest.mark.anyio
async def test_execute_close_decision_long_yes_success():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10, exit_reason="PROFIT_TARGET")
    pos = _make_pos(id=10, side="LONG_YES", status="OPEN", quantity=20.0, entry_price=0.50)
    opp = _make_opp(yes_bid=0.62)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(pos),       # pos query
        _make_exec_result_scalar_one_or_none(opp),       # opp query
        AsyncMock(),                                      # UPDATE td to EXECUTED
    ])

    mock_close_order = MagicMock(id=55)

    with (
        patch("app.services.execution_engine.order_repo.create_order", new_callable=AsyncMock, return_value=mock_close_order),
        patch("app.services.position_service.PositionService") as MockPosSvc,
    ):
        MockPosSvc.return_value.close_position = AsyncMock()
        result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is False
    MockPosSvc.return_value.close_position.assert_awaited_once()


@pytest.mark.anyio
async def test_execute_close_decision_long_no_success():
    td = _make_td(decision="CLOSE_POSITION", target_position_id=10, exit_reason="STOP_LOSS")
    pos = _make_pos(id=10, side="LONG_NO", status="OPEN", quantity=10.0, entry_price=0.50)
    opp = _make_opp(yes_ask=0.38)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result_scalar_one_or_none(pos),
        _make_exec_result_scalar_one_or_none(opp),
        AsyncMock(),
    ])

    mock_close_order = MagicMock(id=66)
    captured_create = {}

    async def capture_create(session, **kwargs):
        captured_create.update(kwargs)
        return mock_close_order

    with (
        patch("app.services.execution_engine.order_repo.create_order", side_effect=capture_create),
        patch("app.services.position_service.PositionService") as MockPosSvc,
    ):
        MockPosSvc.return_value.close_position = AsyncMock()
        result = await ExecutionEngine()._execute_close_decision(session, td)

    assert result is False
    assert captured_create["side"] == "SELL_NO"
    assert captured_create["filled_price"] == pytest.approx(round(1.0 - 0.38, 6))
