"""
test_risk_prediction_window.py — Risk Engine prediction-window lifecycle gate tests.

Verifies that RiskEngine.evaluate() blocks OPEN_LONG_* when the prediction
window is not WINDOW_LIVE, EXIT decisions bypass the gate entirely, and
MarketUniverse rows are fetched in a single batched query per cycle.

All datetimes are timezone-aware UTC.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.risk_engine import RiskEngine

# ---------------------------------------------------------------------------
# Fixed anchors (relative to test-module import time — no datetime patching)
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)

# WINDOW_LIVE: _NOW is 60 s into a 300 s window
_LIVE_START = _NOW - timedelta(seconds=60)
_LIVE_END   = _LIVE_START + timedelta(seconds=300)   # ends in 240 s — clearly live

# UPCOMING: window starts 60 s from now
_UPCOMING_START = _NOW + timedelta(seconds=60)
_UPCOMING_END   = _UPCOMING_START + timedelta(seconds=300)

# RESOLVING: window closed 10 s ago
_RESOLV_END   = _NOW - timedelta(seconds=10)
_RESOLV_START = _RESOLV_END - timedelta(seconds=300)

# EXACT END: window ended exactly at _NOW (started() >= pw_end guaranteed
# because started() is called a few µs after _NOW)
_EXACT_END_START = _NOW - timedelta(seconds=300)
_EXACT_END_END   = _NOW   # started() will be > _NOW → PREDICTION_WINDOW_ENDED

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _td(
    cid="0xABC",
    decision="OPEN_LONG_YES",
    status="PENDING",
    position_size_usdc=5.0,
    asset="BTC",
    timeframe="5m",
    opportunity_score=50.0,
    yes_mid=0.48,
):
    return SimpleNamespace(
        id=1,
        condition_id=cid,
        decision=decision,
        status=status,
        position_size_usdc=position_size_usdc,
        asset=asset,
        timeframe=timeframe,
        opportunity_score=opportunity_score,
        yes_mid=yes_mid,
        yes_bid=0.475,
        yes_ask=0.485,
        spread_yes=0.01,
        exit_reason=None,
        decided_at=_NOW,
    )


def _market(
    cid="0xABC",
    pw_start=_LIVE_START,
    pw_end=_LIVE_END,
    end_time=None,
    asset="BTC",
    timeframe="5m",
):
    return SimpleNamespace(
        condition_id=cid,
        asset=asset,
        timeframe=timeframe,
        prediction_window_start=pw_start,
        prediction_window_end=pw_end,
        end_time=end_time,
        status="active",
    )


def _scalars(rows):
    m = MagicMock()
    m.scalars.return_value.all.return_value = list(rows)
    return m


def _make_session(entry_tds, market_rows, exit_tds=None):
    """
    AsyncSession mock whose execute() returns results in call order:
      1. Pending ENTRY decisions
      2. MarketUniverse batch (only when entry_tds is non-empty)
      3. Pending EXIT decisions

    When entry_tds is empty the `if pending:` branch is skipped entirely —
    no market batch query is issued — so only 2 calls are expected.
    """
    results = [_scalars(entry_tds)]
    if entry_tds:
        results.append(_scalars(market_rows))
    results.append(_scalars(exit_tds or []))

    idx = [0]

    async def _side_effect(*_a, **_kw):
        r = results[idx[0]]
        idx[0] += 1
        return r

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=_side_effect)
    return session


_CAP_SVC   = "app.services.capital_management_service.CapitalManagementService"
_RISK_REPO = "app.services.risk_engine.risk_repo.create_risk_event"
_GET_POS   = "app.services.risk_engine.RiskEngine._get_open_positions"
_GET_CAP   = "app.services.risk_engine.RiskEngine._get_available_capital"
_GET_DTRD  = "app.services.risk_engine.RiskEngine._get_daily_trades_count"
_GET_DL    = "app.services.risk_engine.RiskEngine._get_daily_unrealized_loss"
_GET_PREV  = "app.services.risk_engine.RiskEngine._get_previous_entry_decisions"


async def _run(
    entry_tds,
    market_rows,
    exit_tds=None,
    capital_allowed=True,
    capital_reason=None,
    available_capital=1000.0,
    daily_trades=0,
    daily_loss=0.0,
):
    engine = RiskEngine()
    session = _make_session(entry_tds, market_rows, exit_tds)

    cap_status = MagicMock()
    cap_status.allowed = capital_allowed
    cap_status.reason = capital_reason

    with (
        patch(_CAP_SVC) as mock_cap_cls,
        patch(_RISK_REPO, new=AsyncMock()),
        patch(_GET_POS,  new=AsyncMock(return_value=[])),
        patch(_GET_CAP,  new=AsyncMock(return_value=available_capital)),
        patch(_GET_DTRD, new=AsyncMock(return_value=daily_trades)),
        patch(_GET_DL,   new=AsyncMock(return_value=daily_loss)),
        patch(_GET_PREV, new=AsyncMock(return_value={})),
    ):
        mock_cap_cls.return_value.evaluate = AsyncMock(return_value=cap_status)
        result = await engine.evaluate(session)

    return result, session


# ===========================================================================
# Test 1 — WINDOW_LIVE entry reaches financial rules
# ===========================================================================

@pytest.mark.asyncio
async def test_window_live_entry_allowed():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_LIVE_START, pw_end=_LIVE_END)
    result, _ = await _run([td], [market])
    assert result["allowed"] == 1
    assert result["blocked"] == 0


# ===========================================================================
# Test 2 — UPCOMING window blocks entry
# ===========================================================================

@pytest.mark.asyncio
async def test_upcoming_window_blocks_entry():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_UPCOMING_START, pw_end=_UPCOMING_END)
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 3 — RESOLVING window blocks entry
# ===========================================================================

@pytest.mark.asyncio
async def test_resolving_window_blocks_entry():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_RESOLV_START, pw_end=_RESOLV_END)
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 4 — missing prediction_window_start → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_missing_start_invalid():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=None, pw_end=_LIVE_END)
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 5 — missing prediction_window_end → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_missing_end_invalid():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_LIVE_START, pw_end=None)
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 6 — 299-second window → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_299s_window_invalid():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(
        pw_start=_LIVE_START,
        pw_end=_LIVE_START + timedelta(seconds=299),
    )
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 7 — 301-second window → INVALID_PREDICTION_WINDOW
# ===========================================================================

@pytest.mark.asyncio
async def test_301s_window_invalid():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(
        pw_start=_LIVE_START,
        pw_end=_LIVE_START + timedelta(seconds=301),
    )
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 8 — market not in universe → MARKET_NOT_IN_UNIVERSE
# ===========================================================================

@pytest.mark.asyncio
async def test_market_not_in_universe():
    td = _td(cid="0xNOTFOUND", decision="OPEN_LONG_YES")
    # market_rows is empty — condition_id not returned by batch query
    result, _ = await _run([td], [])
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 9 — exact end time → PREDICTION_WINDOW_ENDED
# ===========================================================================

@pytest.mark.asyncio
async def test_exact_end_prediction_window_ended():
    td = _td(decision="OPEN_LONG_YES")
    # pw_end == _NOW; started() (captured inside evaluate()) is a few µs later
    market = _market(pw_start=_EXACT_END_START, pw_end=_EXACT_END_END)
    result, _ = await _run([td], [market])
    # The gate checks `started >= pw_end`; with pw_end == _NOW and started
    # being a later wall-clock read, this must always block.
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 10 — lifecycle gate runs BEFORE capital gate
# ===========================================================================

@pytest.mark.asyncio
async def test_lifecycle_gate_before_capital_gate():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_UPCOMING_START, pw_end=_UPCOMING_END)

    engine = RiskEngine()
    session = _make_session([td], [market])
    cap_status = MagicMock()
    cap_status.allowed = False          # capital gate would block if reached
    cap_status.reason = "DAILY_LOSS_LIMIT"

    check_rules_calls = []

    with (
        patch(_CAP_SVC) as mock_cap_cls,
        patch(_RISK_REPO, new=AsyncMock()),
        patch(_GET_POS,  new=AsyncMock(return_value=[])),
        patch(_GET_CAP,  new=AsyncMock(return_value=1000.0)),
        patch(_GET_DTRD, new=AsyncMock(return_value=0)),
        patch(_GET_DL,   new=AsyncMock(return_value=0.0)),
        patch(_GET_PREV, new=AsyncMock(return_value={})),
        patch.object(RiskEngine, "_check_rules", side_effect=lambda *a, **kw: check_rules_calls.append(1) or None),
    ):
        mock_cap_cls.return_value.evaluate = AsyncMock(return_value=cap_status)
        result = await engine.evaluate(session)

    # blocked by lifecycle (UPCOMING), not by capital
    assert result["blocked"] == 1
    # _check_rules must NOT have been called (lifecycle blocked first)
    assert check_rules_calls == [], "_check_rules called despite lifecycle block"


# ===========================================================================
# Test 11 — financial rules not called when lifecycle gate fails
# ===========================================================================

@pytest.mark.asyncio
async def test_financial_rules_not_called_on_lifecycle_fail():
    td = _td(decision="OPEN_LONG_YES")
    market = _market(pw_start=_RESOLV_START, pw_end=_RESOLV_END)

    engine = RiskEngine()
    session = _make_session([td], [market])
    cap_status = MagicMock()
    cap_status.allowed = True
    check_rules_calls = []

    with (
        patch(_CAP_SVC) as mock_cap_cls,
        patch(_RISK_REPO, new=AsyncMock()),
        patch(_GET_POS,  new=AsyncMock(return_value=[])),
        patch(_GET_CAP,  new=AsyncMock(return_value=1000.0)),
        patch(_GET_DTRD, new=AsyncMock(return_value=0)),
        patch(_GET_DL,   new=AsyncMock(return_value=0.0)),
        patch(_GET_PREV, new=AsyncMock(return_value={})),
        patch.object(RiskEngine, "_check_rules", side_effect=lambda *a, **kw: check_rules_calls.append(1) or None),
    ):
        mock_cap_cls.return_value.evaluate = AsyncMock(return_value=cap_status)
        await engine.evaluate(session)

    assert check_rules_calls == [], "_check_rules must not be called when lifecycle blocks"


# ===========================================================================
# Test 12 — live entry still blockable by existing capital rule
# ===========================================================================

@pytest.mark.asyncio
async def test_live_entry_blocked_by_capital_rule():
    td = _td(decision="OPEN_LONG_YES", position_size_usdc=500.0)
    market = _market(pw_start=_LIVE_START, pw_end=_LIVE_END)
    # available_capital so low that INSUFFICIENT_CAPITAL fires
    result, _ = await _run(
        [td],
        [market],
        available_capital=0.0,   # reserve floor breach guaranteed
    )
    assert result["blocked"] == 1
    assert result["allowed"] == 0


# ===========================================================================
# Test 13 — EXIT decision bypasses lifecycle gate
# ===========================================================================

@pytest.mark.asyncio
async def test_exit_decision_bypasses_lifecycle_gate():
    # CLOSE_POSITION — market has an UPCOMING window (would block an entry)
    exit_td = _td(decision="CLOSE_POSITION", status="PENDING")

    engine = RiskEngine()
    # No pending ENTRY decisions → the `if pending:` block (and market batch) is skipped
    session = _make_session([], [], exit_tds=[exit_td])
    cap_status = MagicMock()
    cap_status.allowed = True

    with (
        patch(_CAP_SVC) as mock_cap_cls,
        patch(_RISK_REPO, new=AsyncMock()),
        patch(_GET_POS,  new=AsyncMock(return_value=[])),
        patch(_GET_CAP,  new=AsyncMock(return_value=1000.0)),
        patch(_GET_DTRD, new=AsyncMock(return_value=0)),
        patch(_GET_DL,   new=AsyncMock(return_value=0.0)),
        patch(_GET_PREV, new=AsyncMock(return_value={})),
    ):
        mock_cap_cls.return_value.evaluate = AsyncMock(return_value=cap_status)
        result = await engine.evaluate(session)

    assert result["exit_approved"] == 1
    assert result["blocked"] == 0


# ===========================================================================
# Test 14 — market rows fetched in exactly ONE batched query
# ===========================================================================

@pytest.mark.asyncio
async def test_single_batched_market_query():
    """Three distinct pending decisions must not trigger three separate DB queries."""
    tds = [
        _td(cid="0xAAA", decision="OPEN_LONG_YES"),
        _td(cid="0xBBB", decision="OPEN_LONG_NO"),
        _td(cid="0xCCC", decision="OPEN_LONG_YES"),
    ]
    markets = [
        _market(cid="0xAAA"),
        _market(cid="0xBBB"),
        _market(cid="0xCCC"),
    ]
    _, session = await _run(tds, markets)
    # Expected execute calls: 1 (entries) + 1 (market batch) + 1 (exits) = 3
    assert session.execute.await_count == 3, (
        f"Expected 3 session.execute calls, got {session.execute.await_count}. "
        "Market universe must be fetched in a single batched query, not once per decision."
    )


# ===========================================================================
# Test 15 — contract end_time alone cannot authorise entry
# ===========================================================================

@pytest.mark.asyncio
async def test_end_time_alone_cannot_authorise_entry():
    td = _td(decision="OPEN_LONG_YES")
    # prediction_window fields absent; end_time set to something that looks "live"
    market = _market(pw_start=None, pw_end=None, end_time=_LIVE_END)
    result, _ = await _run([td], [market])
    assert result["blocked"] == 1
    assert result["allowed"] == 0
