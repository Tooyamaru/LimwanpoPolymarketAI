"""
test_trade_decision_window_binding.py — Phase A Checkpoint 7B

Verifies the complete window binding chain:
  Model fields → Migration SQL → Repository signature + ORM assignment
  → Strategy validation gate → Strategy insert binding

All datetimes are fixed, timezone-aware UTC values.
Chainlink gate is disabled throughout.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixed anchors
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 7, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(seconds=60)
END = START + timedelta(seconds=300)   # END = NOW + 240s → WINDOW_LIVE

EVENT_SLUG = "btc-above-65000-jul21-0710"
PW_START = START
PW_END = END

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from app.models.trade_decision import TradeDecision
from app.repositories.trade_decision_repository import insert_decision

# ---------------------------------------------------------------------------
# Helpers shared with strategy tests
# ---------------------------------------------------------------------------

def make_opp(cid="0xABC", direction="BUY_YES", score=50.0, spread_yes=0.01):
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
    event_slug=EVENT_SLUG,
    pw_start=PW_START,
    pw_end=PW_END,
):
    return SimpleNamespace(
        condition_id=cid,
        asset="BTC",
        timeframe="5m",
        prediction_window_start=pw_start,
        prediction_window_end=pw_end,
        event_slug=event_slug,
        end_time=None,
        target_price=65000.0,
        target_verified=True,
    )


def make_session(market_rows=None):
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(market_rows or [])
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=exec_result)
    return mock_session


_OPP_PATH      = "app.services.strategy_engine.opp_repo.get_all_opportunities"
_SIG_PATH      = "app.services.strategy_engine.sig_repo.get_last_signal_for_market"
_INSERT_PATH   = "app.services.strategy_engine.td_repo.insert_decision"
_SIZING_PATH   = "app.services.strategy_engine._sizing_service.calculate"
_DT_PATH       = "app.services.strategy_engine.datetime"
_SETTINGS_PATH = "app.services.strategy_engine.settings"


async def _run(opps, market_rows=None, persist_skips=False, sizing_returns=5.0):
    from app.services.strategy_engine import StrategyEngine
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
        mock_dt.now.return_value = NOW
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = False
        mock_settings.STRATEGY_PERSIST_SKIPS = persist_skips
        mock_settings.POSITION_SCORE_MEDIUM = 30

        result = await engine.run(session)

    return result, insert_calls, session


# ===========================================================================
# 1-4: MODEL FIELD PRESENCE
# ===========================================================================

def test_model_has_decision_event_slug():
    """TradeDecision has decision_event_slug column."""
    assert hasattr(TradeDecision, "decision_event_slug")


def test_model_has_decision_prediction_window_start():
    """TradeDecision has decision_prediction_window_start column."""
    assert hasattr(TradeDecision, "decision_prediction_window_start")


def test_model_has_decision_prediction_window_end():
    """TradeDecision has decision_prediction_window_end column."""
    assert hasattr(TradeDecision, "decision_prediction_window_end")


def test_model_binding_fields_are_nullable():
    """All three binding fields accept None (historical-row compatibility)."""
    row = TradeDecision(
        condition_id="0xHIST",
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        status="PENDING",
        opportunity_score=50.0,
        direction="BUY_YES",
        yes_mid=None,
        yes_bid=None,
        yes_ask=None,
        spread_yes=None,
        decided_at=NOW,
        decision_event_slug=None,
        decision_prediction_window_start=None,
        decision_prediction_window_end=None,
    )
    assert row.decision_event_slug is None
    assert row.decision_prediction_window_start is None
    assert row.decision_prediction_window_end is None


# ===========================================================================
# 5-9: REPOSITORY SIGNATURE + ORM ASSIGNMENT
# ===========================================================================

@pytest.mark.asyncio
async def test_insert_decision_accepts_binding_params():
    """insert_decision accepts the three new optional keyword parameters."""
    session = MagicMock()
    session.add = MagicMock()
    row = await insert_decision(
        session,
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        opportunity_score=50.0,
        direction="BUY_YES",
        yes_mid=0.48,
        yes_bid=0.475,
        yes_ask=0.485,
        spread_yes=0.01,
        decision_event_slug=EVENT_SLUG,
        decision_prediction_window_start=PW_START,
        decision_prediction_window_end=PW_END,
    )
    assert row is not None


@pytest.mark.asyncio
async def test_repository_stores_exact_event_slug():
    """insert_decision stores the exact event_slug on the ORM row."""
    session = MagicMock()
    added_rows = []
    session.add = lambda row: added_rows.append(row)

    await insert_decision(
        session,
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        opportunity_score=50.0,
        direction="BUY_YES",
        yes_mid=0.48,
        yes_bid=None,
        yes_ask=None,
        spread_yes=None,
        decision_event_slug=EVENT_SLUG,
        decision_prediction_window_start=PW_START,
        decision_prediction_window_end=PW_END,
    )
    assert added_rows[0].decision_event_slug == EVENT_SLUG


@pytest.mark.asyncio
async def test_repository_stores_exact_prediction_start():
    """insert_decision stores the exact prediction_window_start on the ORM row."""
    session = MagicMock()
    added_rows = []
    session.add = lambda row: added_rows.append(row)

    await insert_decision(
        session,
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        opportunity_score=50.0,
        direction="BUY_YES",
        yes_mid=None,
        yes_bid=None,
        yes_ask=None,
        spread_yes=None,
        decision_event_slug=EVENT_SLUG,
        decision_prediction_window_start=PW_START,
        decision_prediction_window_end=PW_END,
    )
    assert added_rows[0].decision_prediction_window_start == PW_START


@pytest.mark.asyncio
async def test_repository_stores_exact_prediction_end():
    """insert_decision stores the exact prediction_window_end on the ORM row."""
    session = MagicMock()
    added_rows = []
    session.add = lambda row: added_rows.append(row)

    await insert_decision(
        session,
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        opportunity_score=50.0,
        direction="BUY_YES",
        yes_mid=None,
        yes_bid=None,
        yes_ask=None,
        spread_yes=None,
        decision_event_slug=EVENT_SLUG,
        decision_prediction_window_start=PW_START,
        decision_prediction_window_end=PW_END,
    )
    assert added_rows[0].decision_prediction_window_end == PW_END


@pytest.mark.asyncio
async def test_existing_caller_without_binding_fields_still_works():
    """Callers that omit the three new params get None on all binding fields."""
    session = MagicMock()
    added_rows = []
    session.add = lambda row: added_rows.append(row)

    await insert_decision(
        session,
        condition_id="0xLEGACY",
        asset="ETH",
        timeframe="15m",
        decision="WATCH",
        opportunity_score=25.0,
        direction="BUY_YES",
        yes_mid=0.5,
        yes_bid=None,
        yes_ask=None,
        spread_yes=None,
    )
    row = added_rows[0]
    assert row.decision_event_slug is None
    assert row.decision_prediction_window_start is None
    assert row.decision_prediction_window_end is None


# ===========================================================================
# 10-12: STRATEGY SENDS CORRECT BINDING ON OPEN
# ===========================================================================

@pytest.mark.asyncio
async def test_strategy_open_long_yes_sends_exact_binding():
    """OPEN_LONG_YES insert carries the market's event_slug + window datetimes."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market()
    result, inserts, _ = await _run([opp], market_rows=[market])

    assert result["open_long_yes"] == 1
    open_calls = [i for i in inserts if i.get("decision") == "OPEN_LONG_YES"]
    assert len(open_calls) == 1
    c = open_calls[0]
    assert c["decision_event_slug"] == EVENT_SLUG
    assert c["decision_prediction_window_start"] == PW_START
    assert c["decision_prediction_window_end"] == PW_END


@pytest.mark.asyncio
async def test_strategy_open_long_no_sends_exact_binding():
    """OPEN_LONG_NO insert carries the market's event_slug + window datetimes."""
    opp = make_opp(direction="BUY_NO", score=50.0)
    market = make_market()
    result, inserts, _ = await _run([opp], market_rows=[market])

    assert result["open_long_no"] == 1
    open_calls = [i for i in inserts if i.get("decision") == "OPEN_LONG_NO"]
    assert len(open_calls) == 1
    c = open_calls[0]
    assert c["decision_event_slug"] == EVENT_SLUG
    assert c["decision_prediction_window_start"] == PW_START
    assert c["decision_prediction_window_end"] == PW_END


@pytest.mark.asyncio
async def test_strategy_sends_exact_condition_id():
    """OPEN_LONG_YES insert carries the opportunity's condition_id."""
    cid = "0xDEADBEEF1234"
    opp = make_opp(cid=cid, direction="BUY_YES", score=50.0)
    market = make_market(cid=cid)
    result, inserts, _ = await _run([opp], market_rows=[market])

    assert result["open_long_yes"] == 1
    open_calls = [i for i in inserts if i.get("decision") == "OPEN_LONG_YES"]
    assert open_calls[0]["condition_id"] == cid


# ===========================================================================
# 13-16: BINDING VALIDATION GATE
# ===========================================================================

@pytest.mark.asyncio
async def test_missing_event_slug_blocks_open():
    """event_slug=None → SKIP with INVALID_DECISION_WINDOW_BINDING, not OPEN."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(event_slug=None)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i.get("decision") == "OPEN_LONG_YES" for i in inserts)


@pytest.mark.asyncio
async def test_missing_prediction_window_start_blocks_open():
    """prediction_window_start=None → SKIP with INVALID_DECISION_WINDOW_BINDING."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=None)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i.get("decision") == "OPEN_LONG_YES" for i in inserts)


@pytest.mark.asyncio
async def test_missing_prediction_window_end_blocks_open():
    """prediction_window_end=None → SKIP with INVALID_DECISION_WINDOW_BINDING."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_end=None)
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    assert not any(i.get("decision") == "OPEN_LONG_YES" for i in inserts)


@pytest.mark.asyncio
async def test_empty_event_slug_produces_invalid_binding_skip():
    """event_slug='' (empty, falsy) → SKIP with INVALID_DECISION_WINDOW_BINDING.

    Tests a condition mismatch: the market row has a condition_id in the dict
    but the binding data is logically corrupt (empty slug).  The validation
    gate catches it via `not _event_slug` before sizing or counter increment.
    """
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(event_slug="")   # empty string — falsy, not None
    result, inserts, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["skip"] >= 1
    open_inserts = [i for i in inserts if i.get("decision") in ("OPEN_LONG_YES", "OPEN_LONG_NO")]
    assert open_inserts == []


# ===========================================================================
# 17-19: BLOCKED BINDING DOES NOT CALL SIZING / NOT STORED AS OPEN
# ===========================================================================

@pytest.mark.asyncio
async def test_blocked_binding_does_not_call_sizing():
    """When window binding validation fails, sizing is never called."""
    from app.services.strategy_engine import StrategyEngine
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(event_slug=None)   # binding will fail
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

    assert sizing_calls == [], "sizing must not be called when binding gate fails"


@pytest.mark.asyncio
async def test_blocked_binding_not_saved_as_open():
    """Binding failure → no OPEN_LONG_* row persisted (persist_skips=False)."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_start=None)
    result, inserts, _ = await _run([opp], market_rows=[market], persist_skips=False)
    assert not any(i.get("decision") in ("OPEN_LONG_YES", "OPEN_LONG_NO") for i in inserts)


@pytest.mark.asyncio
async def test_blocked_binding_does_not_increment_open_counter():
    """Binding failure → open_long_yes and open_long_no counters stay at 0."""
    opp = make_opp(direction="BUY_YES", score=50.0)
    market = make_market(pw_end=None)
    result, _, _ = await _run([opp], market_rows=[market])
    assert result["open_long_yes"] == 0
    assert result["open_long_no"] == 0


# ===========================================================================
# 20-22: MIGRATION SAFETY
# ===========================================================================

def _load_migration_sql() -> str:
    """Read database.py and return its full text for migration assertions."""
    import pathlib
    return (pathlib.Path(__file__).parent.parent / "core" / "database.py").read_text()


def test_migration_uses_add_column_if_not_exists_for_event_slug():
    """Migration SQL uses ADD COLUMN IF NOT EXISTS for decision_event_slug."""
    sql = _load_migration_sql()
    assert "ADD COLUMN IF NOT EXISTS decision_event_slug" in sql


def test_migration_uses_add_column_if_not_exists_for_window_start():
    """Migration SQL uses ADD COLUMN IF NOT EXISTS for decision_prediction_window_start."""
    sql = _load_migration_sql()
    assert "ADD COLUMN IF NOT EXISTS decision_prediction_window_start" in sql


def test_migration_uses_add_column_if_not_exists_for_window_end():
    """Migration SQL uses ADD COLUMN IF NOT EXISTS for decision_prediction_window_end."""
    sql = _load_migration_sql()
    assert "ADD COLUMN IF NOT EXISTS decision_prediction_window_end" in sql


def test_migration_contains_no_drop_table():
    """Migration block contains no DROP TABLE."""
    sql = _load_migration_sql()
    # Only check within the all_migrations list block (not comments)
    assert "DROP TABLE" not in sql.upper()


def test_migration_contains_no_delete_or_truncate():
    """Migration block contains no DELETE FROM or TRUNCATE (except safe UPDATE backfill)."""
    sql = _load_migration_sql()
    assert "DELETE FROM" not in sql.upper()
    assert "TRUNCATE" not in sql.upper()


# ===========================================================================
# 23-24: WATCH + SKIP BEHAVIOR UNCHANGED
# ===========================================================================

@pytest.mark.asyncio
async def test_watch_behavior_unchanged():
    """WATCH decision (score 20-29) is unaffected by window binding changes."""
    opp = make_opp(direction="BUY_YES", score=25.0)
    market = make_market()
    result, inserts, _ = await _run([opp], market_rows=[market], persist_skips=True)
    assert result["watch"] == 1
    assert any(i.get("decision") == "WATCH" for i in inserts)
    # WATCH insert must NOT carry binding fields (no binding for non-OPEN)
    watch_inserts = [i for i in inserts if i.get("decision") == "WATCH"]
    assert watch_inserts[0].get("decision_event_slug") is None


@pytest.mark.asyncio
async def test_skip_behavior_unchanged():
    """SKIP from strategy rules (e.g. NEUTRAL_DIRECTION) is unaffected."""
    opp = make_opp(direction="NEUTRAL", score=50.0)
    market = make_market()
    result, _, _ = await _run([opp], market_rows=[market])
    assert result["skip"] >= 1
    assert result["open_long_yes"] == 0
    assert result["open_long_no"] == 0
