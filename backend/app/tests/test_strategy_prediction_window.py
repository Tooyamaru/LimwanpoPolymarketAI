"""
test_strategy_prediction_window.py — Strategy Engine prediction-window lifecycle gate tests.

Verifies that StrategyEngine.run() blocks OPEN_LONG_* when the prediction
window is not WINDOW_LIVE, allows WATCH/SKIP regardless of window state,
and performs a single batched MarketUniverse query per cycle.

All datetimes are fixed, timezone-aware UTC values.
Chainlink gate is disabled for all tests here (ENTRY-gate is a separate concern).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.strategy_engine import StrategyEngine

# ---------------------------------------------------------------------------
# Fixed anchors — patch datetime.now to return NOW in all tests
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 7, 0, 0, tzinfo=timezone.utc)

# WINDOW_LIVE: NOW falls inside [START, END)
START = NOW - timedelta(seconds=60)
END = START + timedelta(seconds=300)         # END = NOW + 240s  → LIVE

# UPCOMING: window hasn't started yet
UPCOMING_START = NOW + timedelta(seconds=60)
UPCOMING_END = UPCOMING_START + timedelta(seconds=300)

# RESOLVING: window already closed
RESOLVING_START = NOW - timedelta(seconds=400)
RESOLVING_END = RESOLVING_START + timedelta(seconds=300)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def make_opp(
    cid="0xABC",
    direction="BUY_YES",
    score=50.0,
    spread_yes=0.01,
):
    """Create a minimal Opportunity-like namespace."""
    return SimpleNamespace(
        condition_id=cid,
        asset="BTC",
        timeframe="5m",
        opportunity_score=score,
        direction=direction,
        spread_yes=spread_yes,
        yes_mid=0.48,
        yes_bid=0.475,
        yes_ask=0.485,
    )


def make_market(
    cid="0xABC",
    pw_start=START,
    pw_end=END,
    end_time=None,
    event_slug="btc-above-65000-jul21",
):
    """Create a minimal MarketUniverse-like namespace."""
    return SimpleNamespace(
        condition_id=cid,
        asset="BTC",
        timeframe="5m",
        prediction_window_start=pw_start,
        prediction_window_end=pw_end,
        event_slug=event_slug,
        end_time=end_time,
        target_price=65000.0,
        target_verified=True,
    )


def make_session(market_rows=None):
    """Mock AsyncSession whose execute() returns a batch of market rows."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(market_rows or [])
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=exec_result)

    return mock_session


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_OPP_PATH     = "app.services.strategy_engine.opp_repo.get_all_opportunities"
_SIG_PATH     = "app.services.strategy_engine.sig_repo.get_last_signal_for_market"
_INSERT_PATH  = "app.services.strategy_engine.td_repo.insert_decision"
_SIZING_PATH  = "app.services.strategy_engine._sizing_service.calculate"
_DT_PATH      = "app.services.strategy_engine.datetime"
_SETTINGS_PATH = "app.services.strategy_engine.settings"


async def _run(opps, market_rows=None, persist_skips=False, sizing_returns=5.0):
    engine = StrategyEngine()
    session = make_session(market_rows=market_rows)
    insert_calls = []

    async def _capture_insert(*_, **kw):
        insert_calls.append(kw)
        return MagicMock()

    with (
        patch(_OPP_PATH, new=AsyncMock(return_value=opps)),
        patch(_SIG_PATH, new=AsyncMock(return_value=None)),
        patch(_INSERT_PATH, new=_capture_insert),
        patch(_SIZING_PATH, return_value=sizing_returns),
        patch(_DT_PATH) as mock_dt,
        patch(_SETTINGS_PATH) as mock_settings,
    ):
        # Fix 'now' so lifecycle windows are deterministic
        mock_dt.now.return_value = NOW

        # Disable Chainlink gate; control persist_skips
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = False
        mock_settings.STRATEGY_PERSIST_SKIPS = persist_skips
        mock_settings.POSITION_SCORE_MEDIUM = 30

        result = await engine.run(session)

    return result, insert_calls, session


# ---------------------------------------------------------------------------
# 1. WINDOW_LIVE + OPEN_LONG_YES is saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_long_yes_window_live_is_saved():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=START, pw_end=END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 1
    assert inserts and inserts[0]["decision"] == "OPEN_LONG_YES"


# ---------------------------------------------------------------------------
# 2. WINDOW_LIVE + OPEN_LONG_NO is saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_long_no_window_live_is_saved():
    opp = make_opp(direction="BUY_NO", score=50.0)
    market = make_market(pw_start=START, pw_end=END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_no"] == 1
    assert inserts and inserts[0]["decision"] == "OPEN_LONG_NO"


# ---------------------------------------------------------------------------
# 3. UPCOMING window blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upcoming_window_blocks_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i["decision"] == "OPEN_LONG_YES" for i in inserts)


# ---------------------------------------------------------------------------
# 4. RESOLVING window blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolving_window_blocks_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=RESOLVING_START, pw_end=RESOLVING_END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i["decision"] == "OPEN_LONG_YES" for i in inserts)


# ---------------------------------------------------------------------------
# 5. INVALID missing start blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_start_blocks_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=None, pw_end=END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1


# ---------------------------------------------------------------------------
# 6. INVALID missing end blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_end_blocks_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=START, pw_end=None)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1


# ---------------------------------------------------------------------------
# 7. 299-second window blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_299s_window_blocks_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=START, pw_end=START + timedelta(seconds=299))
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1


# ---------------------------------------------------------------------------
# 8. Market not found in universe blocks OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_market_not_in_universe_blocks_open():
    opp = make_opp(cid="0xNOTFOUND", direction="BUY_YES", score=50.0)
    # market_rows is empty — no row for this condition_id
    result, inserts, _ = await _run([opp], market_rows=[])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i.get("decision") == "OPEN_LONG_YES" for i in inserts)


# ---------------------------------------------------------------------------
# 9. WATCH allowed outside live window (lifecycle gate is OPEN-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_watch_allowed_outside_live_window():
    # score between SCORE_WATCH(20) and SCORE_OPEN(30) → WATCH
    opp = make_opp(direction="BUY_YES", score=25.0)
    # Market has UPCOMING window — but WATCH must not be blocked
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    result, inserts, _ = await _run([opp], market_rows=[market], persist_skips=True)
    assert result["watch"] == 1
    assert any(i["decision"] == "WATCH" for i in inserts)


# ---------------------------------------------------------------------------
# 10. SKIP from strategy logic is always allowed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_allowed_regardless_of_window():
    # direction=NEUTRAL → _make_decision returns SKIP
    opp = make_opp(direction="NEUTRAL", score=50.0)
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    result, _, _ = await _run([opp], market_rows=[market])
    assert result["skip"] >= 1
    assert result["open_long_yes"] == 0
    assert result["open_long_no"] == 0


# ---------------------------------------------------------------------------
# 11. Blocked OPEN does not call sizing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blocked_open_does_not_call_sizing():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    engine = StrategyEngine()
    session = make_session(market_rows=[market])
    sizing_calls = []

    def _capture_sizing(score):
        sizing_calls.append(score)
        return 5.0

    with (
        patch(_OPP_PATH, new=AsyncMock(return_value=[opp])),
        patch(_SIG_PATH, new=AsyncMock(return_value=None)),
        patch(_INSERT_PATH, new=AsyncMock(return_value=MagicMock())),
        patch(_SIZING_PATH, side_effect=_capture_sizing),
        patch(_DT_PATH) as mock_dt,
        patch(_SETTINGS_PATH) as mock_settings,
    ):
        mock_dt.now.return_value = NOW
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = False
        mock_settings.STRATEGY_PERSIST_SKIPS = False
        mock_settings.POSITION_SCORE_MEDIUM = 30
        await engine.run(session)

    assert sizing_calls == [], "sizing must not be called when lifecycle gate blocks"


# ---------------------------------------------------------------------------
# 12. Blocked OPEN does not call insert_decision as OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blocked_open_not_inserted_as_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=RESOLVING_START, pw_end=RESOLVING_END)
    # persist_skips=False → no insert at all for a blocked OPEN
    result, inserts, _ = await _run([opp], market_rows=[market], persist_skips=False)
    assert not any(i.get("decision") in ("OPEN_LONG_YES", "OPEN_LONG_NO") for i in inserts)


# ---------------------------------------------------------------------------
# 13. Open counter does not increment when blocked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_counter_not_incremented_when_blocked():
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    result, _, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["open_long_no"] == 0


# ---------------------------------------------------------------------------
# 14. Market rows are fetched in a single batched query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_batched_query_for_market_rows():
    opps = [
        make_opp(cid="0xAAA", direction="BUY_YES", score=50.0),
        make_opp(cid="0xBBB", direction="BUY_NO",  score=50.0),
        make_opp(cid="0xCCC", direction="BUY_YES", score=50.0),
    ]
    markets = [
        make_market(cid="0xAAA"),
        make_market(cid="0xBBB"),
        make_market(cid="0xCCC"),
    ]
    _, _, session = await _run(opps, market_rows=markets)
    # session.execute called exactly once (the batch MarketUniverse fetch)
    assert session.execute.await_count == 1


# ---------------------------------------------------------------------------
# 15. Contract end_time alone cannot authorise OPEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_time_alone_cannot_authorise_open():
    opp = make_opp(direction="BUY_YES", score=50.0)
    # prediction_window fields absent; end_time set to a live-looking value
    market = make_market(pw_start=None, pw_end=None, end_time=END)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert not any(i.get("decision") == "OPEN_LONG_YES" for i in inserts)
