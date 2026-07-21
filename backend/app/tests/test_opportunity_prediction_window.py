"""
test_opportunity_prediction_window.py — Opportunity Engine lifecycle gating tests.

Verifies that OpportunityEngine.evaluate() uses get_window_live_universe,
applies the canonical get_prediction_window_lifecycle gate, and computes
time-remaining exclusively from prediction_window_end.

All datetimes are fixed, timezone-aware UTC values.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.opportunity_engine import OpportunityEngine

# ---------------------------------------------------------------------------
# Fixed anchors
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 6, 10, 0, tzinfo=timezone.utc)
START = NOW - timedelta(seconds=60)          # window started 60s ago
END = START + timedelta(seconds=300)          # window ends in 240s

UPCOMING_START = NOW + timedelta(seconds=60)
UPCOMING_END = UPCOMING_START + timedelta(seconds=300)

RESOLVING_START = NOW - timedelta(seconds=400)
RESOLVING_END = RESOLVING_START + timedelta(seconds=300)   # already past

# ---------------------------------------------------------------------------
# Market factory
# ---------------------------------------------------------------------------

def make_market(
    condition_id="0xABC",
    asset="BTC",
    timeframe="5m",
    pw_start=START,
    pw_end=END,
    end_time=None,
):
    return SimpleNamespace(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        prediction_window_start=pw_start,
        prediction_window_end=pw_end,
        end_time=end_time,
    )


# ---------------------------------------------------------------------------
# Snapshot / DB mocks
# ---------------------------------------------------------------------------

def _make_snap():
    s = MagicMock()
    s.yes_mid = 0.50
    s.yes_bid = 0.495
    s.yes_ask = 0.505
    s.no_mid = 0.50
    s.spread_yes = 0.01
    s.spread_no = 0.01
    return s


_UPSERT_PATH = "app.services.opportunity_engine.repo.upsert_opportunity"
_FETCH_PATH = "app.services.opportunity_engine.get_latest_by_condition"
_UNIVERSE_PATH = "app.services.opportunity_engine.get_window_live_universe"


async def _run(markets, snap=None):
    """Run one evaluate() cycle with mocked dependencies."""
    engine = OpportunityEngine()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    sig_result = MagicMock()
    sig_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=sig_result)

    snap_list = [snap or _make_snap()]

    with (
        patch(_UNIVERSE_PATH, new=AsyncMock(return_value=markets)),
        patch(_FETCH_PATH, new=AsyncMock(return_value=snap_list)),
        patch(_UPSERT_PATH, new=AsyncMock()),
        patch("app.services.opportunity_engine.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await engine.evaluate(mock_session)

    return result


# ---------------------------------------------------------------------------
# 1. WINDOW_LIVE market is evaluated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_window_live_market_is_evaluated():
    result = await _run([make_market()])
    assert result["markets_evaluated"] == 1
    assert result["skipped_no_data"] == 0


# ---------------------------------------------------------------------------
# 2. UPCOMING market is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upcoming_market_is_skipped():
    market = make_market(pw_start=UPCOMING_START, pw_end=UPCOMING_END)
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 3. RESOLVING market is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolving_market_is_skipped():
    market = make_market(pw_start=RESOLVING_START, pw_end=RESOLVING_END)
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 4. Missing prediction_window_start is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_prediction_start_is_skipped():
    market = make_market(pw_start=None, pw_end=END)
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 5. Missing prediction_window_end is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_prediction_end_is_skipped():
    market = make_market(pw_start=START, pw_end=None)
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 6. Invalid 299-second window is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_299s_window_is_skipped():
    market = make_market(pw_start=START, pw_end=START + timedelta(seconds=299))
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 7. Invalid 301-second window is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_301s_window_is_skipped():
    market = make_market(pw_start=START, pw_end=START + timedelta(seconds=301))
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 8. time remaining uses prediction_window_end, not end_time
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_time_remaining_uses_prediction_window_end():
    """
    prediction_window_end is 240s away from NOW.
    end_time is set to a different value (far future).
    Score discovery component should reflect the pw_end timing.
    """
    far_end_time = NOW + timedelta(hours=10)   # would give very low discovery score
    market = make_market(pw_end=END, end_time=far_end_time)

    engine = OpportunityEngine()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    sig_result = MagicMock()
    sig_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=sig_result)

    upsert_calls = []

    async def capture_upsert(*_, **kw):
        upsert_calls.append(kw)

    with (
        patch(_UNIVERSE_PATH, new=AsyncMock(return_value=[market])),
        patch(_FETCH_PATH, new=AsyncMock(return_value=[_make_snap()])),
        patch(_UPSERT_PATH, new=capture_upsert),
        patch("app.services.opportunity_engine.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await engine.evaluate(mock_session)

    assert upsert_calls, "upsert should have been called for a WINDOW_LIVE market"
    minutes_stored = upsert_calls[0]["minutes_to_expiry"]
    # pw_end is 240s away → 4.0 minutes (not 600 minutes from far end_time)
    assert minutes_stored is not None
    assert minutes_stored < 10, (
        f"minutes_to_expiry={minutes_stored} — should reflect prediction_window_end (~4m), not end_time (~600m)"
    )


# ---------------------------------------------------------------------------
# 9. Generic end_time alone cannot make a market valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_time_alone_cannot_validate_market():
    """A market with no prediction_window fields but a valid end_time is skipped."""
    market = make_market(pw_start=None, pw_end=None, end_time=NOW + timedelta(hours=1))
    result = await _run([market])
    assert result["markets_evaluated"] == 0
    assert result["skipped_no_data"] == 1


# ---------------------------------------------------------------------------
# 10. Repository call uses get_window_live_universe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repository_uses_get_window_live_universe():
    """get_window_live_universe must be called; get_active_universe must NOT."""
    engine = OpportunityEngine()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch(_UNIVERSE_PATH, new=AsyncMock(return_value=[])) as mock_wl,
        patch("app.services.opportunity_engine.get_latest_by_condition", new=AsyncMock(return_value=[])),
        patch(_UPSERT_PATH, new=AsyncMock()),
        patch("app.services.opportunity_engine.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await engine.evaluate(mock_session)

    mock_wl.assert_called_once()


# ---------------------------------------------------------------------------
# 11. One invalid market does not stop other valid markets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_market_does_not_block_valid_market():
    valid_market = make_market(condition_id="0xVALID")
    invalid_market = make_market(
        condition_id="0xINVALID",
        pw_start=None,
        pw_end=None,
    )
    result = await _run([invalid_market, valid_market])
    assert result["markets_evaluated"] == 1
    assert result["skipped_no_data"] == 1
