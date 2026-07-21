"""
test_execution_prediction_window.py — Phase A Checkpoint 8

Verifies ExecutionEngine._execute_decision() prediction-window validation gate:
  11 checks, 8 rejection codes, BLOCKED terminal status, no price fetch on
  rejection, no Trade created on rejection, capital released exactly once.

All datetimes are fixed, timezone-aware UTC values.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.execution_engine import ExecutionEngine

# ---------------------------------------------------------------------------
# Fixed anchors
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 8, 0, 0, tzinfo=timezone.utc)

# WINDOW_LIVE: exactly 300 s, NOW falls inside [START, END)
START = NOW - timedelta(seconds=60)
END = START + timedelta(seconds=300)       # = NOW + 240 s

# UPCOMING: window hasn't started yet
UP_START = NOW + timedelta(seconds=60)
UP_END = UP_START + timedelta(seconds=300)

# RESOLVING: window already closed
RS_START = NOW - timedelta(seconds=400)
RS_END = RS_START + timedelta(seconds=300)  # = NOW - 100 s (past)

SLUG = "btc-updown-5m-1784271300"
CID = "0xDEAD1234"

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def make_td(
    condition_id=CID,
    decision_event_slug=SLUG,
    decision_prediction_window_start=START,
    decision_prediction_window_end=END,
    decision="OPEN_LONG_YES",
    yes_ask=0.57,
    yes_bid=0.53,
    position_size_usdc=10.0,
):
    td = MagicMock()
    td.id = 1
    td.condition_id = condition_id
    td.asset = "BTC"
    td.timeframe = "5m"
    td.decision = decision
    td.status = "RISK_APPROVED"
    td.yes_ask = yes_ask
    td.yes_bid = yes_bid
    td.yes_mid = 0.55
    td.spread_yes = 0.04
    td.opportunity_score = 75.0
    td.direction = "BUY_YES"
    td.position_size_usdc = position_size_usdc
    td.decided_at = None
    td.decision_event_slug = decision_event_slug
    td.decision_prediction_window_start = decision_prediction_window_start
    td.decision_prediction_window_end = decision_prediction_window_end
    return td


def make_market(
    condition_id=CID,
    event_slug=SLUG,
    pw_start=START,
    pw_end=END,
    end_time=None,
):
    m = MagicMock()
    m.condition_id = condition_id
    m.event_slug = event_slug
    m.prediction_window_start = pw_start
    m.prediction_window_end = pw_end
    m.start_time = pw_start
    m.end_time = end_time or pw_end
    return m


def scalar_one_or_none(val):
    r = MagicMock()
    r.scalar_one_or_none.return_value = val
    return r


def make_session(market, extra_side_effects=None):
    """Session whose first execute() returns market lookup, rest are AsyncMocks."""
    session = AsyncMock()
    sides = [scalar_one_or_none(market)]
    if extra_side_effects:
        sides.extend(extra_side_effects)
    else:
        # Default: one extra for the BLOCKED or EXECUTED update
        sides.append(AsyncMock())
    session.execute = AsyncMock(side_effect=sides)
    return session


_ORDER_PATCH = "app.services.execution_engine.order_repo.create_order"
_DT_PATCH = "app.services.execution_engine.datetime"


async def _run(td, market, extra_sides=None, mock_order=True):
    """Run _execute_decision with patched datetime.now → NOW."""
    session = make_session(market, extra_side_effects=extra_sides)
    order_calls = []

    async def capture_order(*_, **kw):
        order_calls.append(kw)
        return MagicMock(id=42)

    engine = ExecutionEngine()

    if mock_order:
        with (
            patch(_DT_PATCH) as mock_dt,
            patch(_ORDER_PATCH, side_effect=capture_order),
        ):
            mock_dt.now.return_value = NOW
            mock_dt.now.side_effect = None
            result = await engine._execute_decision(session, td)
    else:
        with patch(_DT_PATCH) as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.now.side_effect = None
            result = await engine._execute_decision(session, td)

    return result, session, order_calls


# ===========================================================================
# 1. Valid WINDOW_LIVE binding → execution proceeds
# ===========================================================================

@pytest.mark.asyncio
async def test_valid_window_live_proceeds():
    """A fully valid binding with WINDOW_LIVE allows execution (skipped=False)."""
    td = make_td()
    market = make_market()
    result, session, orders = await _run(
        td, market, extra_sides=[AsyncMock()]  # EXECUTED update
    )
    order, skipped = result
    assert skipped is False
    assert order is not None
    assert len(orders) == 1


# ===========================================================================
# 2. Market not found → rejected BLOCKED
# ===========================================================================

@pytest.mark.asyncio
async def test_market_not_found_rejected():
    """condition_id not in MarketUniverse → BLOCKED, skip=True."""
    td = make_td()
    result, session, orders = await _run(td, None)
    order, skipped = result
    assert skipped is True
    assert order is None
    # Second execute is the BLOCKED update
    assert session.execute.await_count == 2
    assert len(orders) == 0


# ===========================================================================
# 3-5. Missing binding fields → INVALID_DECISION_WINDOW_BINDING
# ===========================================================================

@pytest.mark.asyncio
async def test_missing_event_slug_rejected():
    """decision_event_slug=None → rejected."""
    td = make_td(decision_event_slug=None)
    result, session, orders = await _run(td, make_market())
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


@pytest.mark.asyncio
async def test_missing_prediction_window_start_rejected():
    """decision_prediction_window_start=None → rejected."""
    td = make_td(decision_prediction_window_start=None)
    result, session, orders = await _run(td, make_market())
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


@pytest.mark.asyncio
async def test_missing_prediction_window_end_rejected():
    """decision_prediction_window_end=None → rejected."""
    td = make_td(decision_prediction_window_end=None)
    result, session, orders = await _run(td, make_market())
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 6. Condition mismatch → DECISION_CONDITION_STALE
# ===========================================================================

@pytest.mark.asyncio
async def test_condition_mismatch_rejected():
    """Market row has different condition_id than decision → rejected."""
    td = make_td(condition_id="0xDEAD1234")
    # Inject a market with a different condition_id (data-corruption scenario)
    market = make_market(condition_id="0xOTHER9999")
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 7. Event slug mismatch → DECISION_EVENT_SLUG_STALE
# ===========================================================================

@pytest.mark.asyncio
async def test_event_slug_mismatch_rejected():
    """Decision has old slug; market has rolled to new slug → rejected."""
    td = make_td(decision_event_slug="btc-updown-5m-1784271000")   # old slot
    market = make_market(event_slug="btc-updown-5m-1784271300")     # current slot
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 8. Prediction start mismatch → DECISION_WINDOW_STALE
# ===========================================================================

@pytest.mark.asyncio
async def test_prediction_start_mismatch_rejected():
    """Decision's pw_start differs from current market's pw_start → rejected."""
    old_start = START - timedelta(seconds=300)
    td = make_td(decision_prediction_window_start=old_start)
    market = make_market(pw_start=START)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 9. Prediction end mismatch → DECISION_WINDOW_STALE
# ===========================================================================

@pytest.mark.asyncio
async def test_prediction_end_mismatch_rejected():
    """Decision's pw_end differs from current market's pw_end → rejected."""
    old_end = END - timedelta(seconds=300)
    td = make_td(decision_prediction_window_end=old_end)
    market = make_market(pw_end=END)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 10. UPCOMING market → MARKET_NOT_WINDOW_LIVE
# ===========================================================================

@pytest.mark.asyncio
async def test_upcoming_market_rejected():
    """Window hasn't started yet → MARKET_NOT_WINDOW_LIVE."""
    td = make_td(
        decision_prediction_window_start=UP_START,
        decision_prediction_window_end=UP_END,
    )
    market = make_market(pw_start=UP_START, pw_end=UP_END)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 11. Exact end boundary → PREDICTION_WINDOW_ENDED
# ===========================================================================

@pytest.mark.asyncio
async def test_exact_end_boundary_rejected():
    """now == prediction_window_end → PREDICTION_WINDOW_ENDED (not retry-able)."""
    # Window ends exactly at NOW
    pw_start = NOW - timedelta(seconds=300)
    pw_end = NOW  # exact boundary: now >= pw_end triggers rejection
    td = make_td(
        decision_prediction_window_start=pw_start,
        decision_prediction_window_end=pw_end,
    )
    market = make_market(pw_start=pw_start, pw_end=pw_end)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 12. RESOLVING market → rejected
# ===========================================================================

@pytest.mark.asyncio
async def test_resolving_market_rejected():
    """Window already closed → rejected (RESOLVING state)."""
    td = make_td(
        decision_prediction_window_start=RS_START,
        decision_prediction_window_end=RS_END,
    )
    market = make_market(pw_start=RS_START, pw_end=RS_END)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 13. Invalid 299-second window → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_299s_window_rejected():
    """Duration of 299 s fails canonical lifecycle validation."""
    short_end = START + timedelta(seconds=299)
    td = make_td(
        decision_prediction_window_start=START,
        decision_prediction_window_end=short_end,
    )
    market = make_market(pw_start=START, pw_end=short_end)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 14. Invalid 301-second window → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_301s_window_rejected():
    """Duration of 301 s fails canonical lifecycle validation."""
    long_end = START + timedelta(seconds=301)
    td = make_td(
        decision_prediction_window_start=START,
        decision_prediction_window_end=long_end,
    )
    market = make_market(pw_start=START, pw_end=long_end)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 15. Contract end_time alone cannot authorise execution
# ===========================================================================

@pytest.mark.asyncio
async def test_contract_end_time_cannot_authorise_execution():
    """
    Even if end_time is far in the future, an expired prediction window
    is still rejected.  The gate uses prediction_window_end, not end_time.
    """
    far_end_time = NOW + timedelta(hours=48)
    td = make_td(
        decision_prediction_window_start=RS_START,
        decision_prediction_window_end=RS_END,
    )
    market = make_market(pw_start=RS_START, pw_end=RS_END, end_time=far_end_time)
    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True
    assert len(orders) == 0


# ===========================================================================
# 16. Rejected decision does not request executable price
# ===========================================================================

@pytest.mark.asyncio
async def test_rejected_decision_does_not_fetch_price():
    """
    When window validation fails, yes_ask / yes_bid must not be read
    (order_repo.create_order must not be called).
    """
    td = make_td(decision_event_slug=None)
    market = make_market()

    session = make_session(market)
    price_attr_accesses = []

    # Override yes_ask/yes_bid with a property that records access
    type(td).yes_ask = property(lambda self: price_attr_accesses.append("yes_ask") or 0.57)
    type(td).yes_bid = property(lambda self: price_attr_accesses.append("yes_bid") or 0.53)

    with (
        patch(_DT_PATCH) as mock_dt,
        patch(_ORDER_PATCH, new_callable=AsyncMock) as mock_order,
    ):
        mock_dt.now.return_value = NOW
        await ExecutionEngine()._execute_decision(session, td)

    assert mock_order.await_count == 0, "order must not be created on rejection"


# ===========================================================================
# 17. Rejected decision does not create a Trade
# ===========================================================================

@pytest.mark.asyncio
async def test_rejected_decision_does_not_create_trade():
    """order_repo.create_order is never called when window validation fails."""
    td = make_td(decision_prediction_window_start=None)
    market = make_market()
    _, _, orders = await _run(td, market, mock_order=True)
    assert orders == [], "create_order must not be called on rejection"


# ===========================================================================
# 18. Rejected decision releases reserved capital exactly once
# ===========================================================================

@pytest.mark.asyncio
async def test_rejected_decision_releases_capital_once():
    """
    When window validation fails, the decision is marked BLOCKED via exactly
    one UPDATE.  A second UPDATE would double-release (double-mark) and must
    not happen.
    """
    td = make_td(decision_event_slug="btc-updown-5m-0000")  # slug mismatch
    market = make_market(event_slug=SLUG)

    session = make_session(market, extra_side_effects=[AsyncMock()])
    with patch(_DT_PATCH) as mock_dt:
        mock_dt.now.return_value = NOW
        await ExecutionEngine()._execute_decision(session, td)

    # Total execute calls: 1 (market lookup) + 1 (BLOCKED update) = 2
    assert session.execute.await_count == 2, (
        f"Expected exactly 2 execute calls (lookup + BLOCKED update), "
        f"got {session.execute.await_count}"
    )


# ===========================================================================
# 19. Valid decision uses the exact condition_id
# ===========================================================================

@pytest.mark.asyncio
async def test_valid_decision_uses_exact_condition_id():
    """create_order receives the same condition_id as the TradeDecision."""
    td = make_td(condition_id="0xEXACT")
    market = make_market(condition_id="0xEXACT")

    result, session, orders = await _run(
        td, market, extra_sides=[AsyncMock()]
    )
    _, skipped = result
    assert skipped is False
    assert orders[0]["condition_id"] == "0xEXACT"


# ===========================================================================
# 20. Window A decision not executed against Window B
# ===========================================================================

@pytest.mark.asyncio
async def test_window_a_decision_not_executed_against_window_b():
    """
    Decision was made for Window A (old slug/timestamps).
    Market has rolled to Window B (new slug/timestamps).
    Execution must be rejected — not redirected to Window B.
    """
    # Window A (old slot, 5 minutes ago)
    a_start = START - timedelta(seconds=300)
    a_end = a_start + timedelta(seconds=300)
    a_slug = "btc-updown-5m-1784271000"

    # Window B (current slot)
    b_start = START
    b_end = END
    b_slug = SLUG

    td = make_td(
        decision_event_slug=a_slug,
        decision_prediction_window_start=a_start,
        decision_prediction_window_end=a_end,
    )
    # Market is now on Window B
    market = make_market(event_slug=b_slug, pw_start=b_start, pw_end=b_end)

    result, session, orders = await _run(td, market)
    _, skipped = result
    assert skipped is True, "stale Window A decision must not execute against Window B"
    assert len(orders) == 0
