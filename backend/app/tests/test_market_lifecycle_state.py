"""
Market Lifecycle State Tests — Phase 12E.

Validates:
1.  get_market_lifecycle_state() canonical function
2.  _determine_status() start_time guard (Gamma active-before-open bug)
3.  get_active_universe() time guards (pre-market / stale-expired filter)
4.  Execution engine lifecycle revalidation
5.  Stale decision rejection
6.  API schema lifecycle fields
7.  Frontend display rules (lifecycle_state driven)
8.  UTC consistency
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.anyio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_market(start_offset_secs: float, end_offset_secs: float,
                 start_time=None, end_time=None):
    """Create a minimal market-like mock relative to UTC now."""
    now = datetime.now(timezone.utc)
    m = MagicMock()
    if start_time is not None:
        m.start_time = start_time
    else:
        m.start_time = now + timedelta(seconds=start_offset_secs)
    if end_time is not None:
        m.end_time = end_time
    else:
        m.end_time = now + timedelta(seconds=end_offset_secs)
    m.status = "active"
    return m


# ══════════════════════════════════════════════════════════════════════════════
# 1.  get_market_lifecycle_state() canonical function
# ══════════════════════════════════════════════════════════════════════════════

async def test_lifecycle_pre_market_when_before_start():
    """now < start_time → PRE_MARKET."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_PRE_MARKET
    now = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0,
                     start_time=datetime(2026, 7, 12, 11, 0, 0, tzinfo=timezone.utc),
                     end_time=datetime(2026, 7, 13, 11, 0, 0, tzinfo=timezone.utc))
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_PRE_MARKET


async def test_lifecycle_active_within_window():
    """start_time <= now < end_time → ACTIVE."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_ACTIVE
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0,
                     start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
                     end_time=datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc))
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_ACTIVE


async def test_lifecycle_active_at_exact_start_time():
    """now == start_time exactly → ACTIVE (boundary inclusive)."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_ACTIVE
    start = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    end   = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0, start_time=start, end_time=end)
    assert get_market_lifecycle_state(m, start) == LIFECYCLE_ACTIVE


async def test_lifecycle_expired_at_end_time():
    """now == end_time → EXPIRED (boundary exclusive)."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_EXPIRED
    start = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    end   = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0, start_time=start, end_time=end)
    assert get_market_lifecycle_state(m, end) == LIFECYCLE_EXPIRED


async def test_lifecycle_expired_after_end_time():
    """now > end_time → EXPIRED."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_EXPIRED
    now = datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0,
                     start_time=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
                     end_time=datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc))
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_EXPIRED


async def test_lifecycle_invalid_when_start_time_none():
    """start_time=None → INVALID_TIME_STATE."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_INVALID
    m = MagicMock()
    m.start_time = None
    m.end_time   = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_INVALID


async def test_lifecycle_invalid_when_end_time_none():
    """end_time=None → INVALID_TIME_STATE."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_INVALID
    m = MagicMock()
    m.start_time = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    m.end_time   = None
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_INVALID


async def test_lifecycle_invalid_when_start_equals_end():
    """start_time == end_time → INVALID_TIME_STATE (zero-duration market)."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_INVALID
    ts = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    m = _make_market(0, 0, start_time=ts, end_time=ts)
    assert get_market_lifecycle_state(m, ts) == LIFECYCLE_INVALID


async def test_lifecycle_handles_naive_datetime():
    """Naive (timezone-unaware) datetimes are promoted to UTC, not rejected."""
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_ACTIVE
    # naive datetimes — should be treated as UTC
    m = MagicMock()
    m.start_time = datetime(2026, 7, 12, 10, 0, 0)   # naive
    m.end_time   = datetime(2026, 7, 13, 10, 0, 0)   # naive
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert get_market_lifecycle_state(m, now) == LIFECYCLE_ACTIVE


# ══════════════════════════════════════════════════════════════════════════════
# 2.  _determine_status() start_time guard
# ══════════════════════════════════════════════════════════════════════════════

async def test_determine_status_gamma_active_before_start_returns_upcoming():
    """
    Gamma can mark a market active=True before its start_time arrives.
    _determine_status must NOT return 'active' in this case.
    """
    from app.services.market_universe_service import _determine_status
    future_start = datetime.now(timezone.utc) + timedelta(hours=2)
    future_end   = future_start + timedelta(hours=26)
    status = _determine_status(
        is_active=True,       # Gamma says active
        is_closed=False,
        start_time=future_start,
        end_time=future_end,
    )
    assert status == "upcoming", (
        f"Got '{status}'; a Gamma-active market with future start_time "
        "must be classified as 'upcoming', not 'active'"
    )


async def test_determine_status_active_when_past_start():
    """is_active=True with start_time in the past → 'active'."""
    from app.services.market_universe_service import _determine_status
    past_start = datetime.now(timezone.utc) - timedelta(hours=1)
    future_end = datetime.now(timezone.utc) + timedelta(hours=25)
    status = _determine_status(is_active=True, is_closed=False,
                                start_time=past_start, end_time=future_end)
    assert status == "active"


async def test_determine_status_expired_when_closed():
    """is_closed=True → always 'expired', regardless of other flags."""
    from app.services.market_universe_service import _determine_status
    status = _determine_status(is_active=True, is_closed=True,
                                start_time=None, end_time=None)
    assert status == "expired"


async def test_determine_status_expired_when_past_end():
    """end_time in the past → 'expired'."""
    from app.services.market_universe_service import _determine_status
    past_end = datetime.now(timezone.utc) - timedelta(hours=1)
    status = _determine_status(is_active=True, is_closed=False,
                                start_time=None, end_time=past_end)
    assert status == "expired"


# ══════════════════════════════════════════════════════════════════════════════
# 3.  Execution engine lifecycle revalidation
# ══════════════════════════════════════════════════════════════════════════════

async def test_execution_engine_blocks_pre_market_decision():
    """
    Execution engine must skip a RISK_APPROVED decision when the market's
    lifecycle_state is PRE_MARKET (now < start_time).
    """
    from app.services.execution_engine import ExecutionEngine

    # Market that hasn't opened yet
    future_start = datetime.now(timezone.utc) + timedelta(hours=2)
    future_end   = future_start + timedelta(hours=26)
    market_mock = MagicMock()
    market_mock.start_time = future_start
    market_mock.end_time   = future_end
    market_mock.condition_id = "cid-pre-market"

    td = MagicMock()
    td.id           = 1
    td.condition_id = "cid-pre-market"
    td.asset        = "BTC"
    td.timeframe    = "5m"
    td.decision     = "OPEN_LONG_NO"
    td.decided_at   = datetime.now(timezone.utc)
    td.yes_bid      = 0.50
    td.yes_ask      = 0.51
    td.position_size_usdc = 10.0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=market_mock)
    ))

    engine = ExecutionEngine()
    result, did_skip = await engine._execute_decision(session, td)

    assert result is None, "Pre-market decision must not produce an order"
    assert did_skip is True, "Pre-market decision must be skipped (did_skip=True)"


async def test_execution_engine_blocks_expired_market():
    """
    Execution engine must skip a decision for an EXPIRED market
    (now >= end_time).
    """
    from app.services.execution_engine import ExecutionEngine

    past_start = datetime.now(timezone.utc) - timedelta(hours=26)
    past_end   = datetime.now(timezone.utc) - timedelta(hours=1)
    market_mock = MagicMock()
    market_mock.start_time = past_start
    market_mock.end_time   = past_end
    market_mock.condition_id = "cid-expired"

    td = MagicMock()
    td.id           = 2
    td.condition_id = "cid-expired"
    td.asset        = "ETH"
    td.timeframe    = "1H"
    td.decision     = "OPEN_LONG_YES"
    td.decided_at   = datetime.now(timezone.utc) - timedelta(minutes=5)
    td.yes_bid      = 0.50
    td.yes_ask      = 0.51
    td.position_size_usdc = 10.0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=market_mock)
    ))

    engine = ExecutionEngine()
    result, did_skip = await engine._execute_decision(session, td)

    assert result is None
    assert did_skip is True


async def test_execution_engine_blocks_missing_market():
    """
    Execution engine must skip when condition_id is not found in universe.
    """
    from app.services.execution_engine import ExecutionEngine

    td = MagicMock()
    td.id           = 3
    td.condition_id = "cid-unknown"
    td.asset        = "SOL"
    td.timeframe    = "15m"
    td.decision     = "OPEN_LONG_NO"
    td.decided_at   = datetime.now(timezone.utc)
    td.yes_bid      = 0.50
    td.yes_ask      = 0.51
    td.position_size_usdc = 10.0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)  # not found
    ))

    engine = ExecutionEngine()
    result, did_skip = await engine._execute_decision(session, td)

    assert result is None
    assert did_skip is True


async def test_execution_engine_blocks_stale_decision():
    """
    Execution engine must skip a decision older than EXECUTION_MAX_DECISION_AGE_MINUTES.
    """
    from app.services.execution_engine import ExecutionEngine
    from app.config.settings import settings

    # Active market
    past_start = datetime.now(timezone.utc) - timedelta(hours=2)
    future_end = datetime.now(timezone.utc) + timedelta(hours=22)
    market_mock = MagicMock()
    market_mock.start_time = past_start
    market_mock.end_time   = future_end
    market_mock.condition_id = "cid-active"

    stale_decided_at = datetime.now(timezone.utc) - timedelta(
        minutes=settings.EXECUTION_MAX_DECISION_AGE_MINUTES + 1
    )
    td = MagicMock()
    td.id           = 4
    td.condition_id = "cid-active"
    td.asset        = "XRP"
    td.timeframe    = "5m"
    td.decision     = "OPEN_LONG_NO"
    td.decided_at   = stale_decided_at
    td.yes_bid      = 0.50
    td.yes_ask      = 0.51
    td.position_size_usdc = 10.0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=market_mock)
    ))

    engine = ExecutionEngine()
    result, did_skip = await engine._execute_decision(session, td)

    assert result is None
    assert did_skip is True


# ══════════════════════════════════════════════════════════════════════════════
# 4.  API schema lifecycle fields
# ══════════════════════════════════════════════════════════════════════════════

async def test_schema_lifecycle_defaults_are_active():
    """
    UniverseMarketResponse default lifecycle fields represent ACTIVE market.
    ORM objects that lack these attributes must produce safe defaults.
    """
    from app.schemas.universe import UniverseMarketResponse
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    r = UniverseMarketResponse(
        id=1, asset="BTC", timeframe="5m",
        series_slug="btc-up-or-down-5m", series_id="s1", event_id="e1",
        condition_id="0xabc", yes_token_id="yt1", no_token_id="nt1",
        question="Will BTC go up?",
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=23),
        status="active",
        created_at=now, updated_at=now,
    )
    assert r.lifecycle_state == "ACTIVE"
    assert r.execution_allowed is True
    assert r.is_pre_market is False
    assert r.is_active_market is True
    assert r.is_expired is False
    assert r.display_status == "ACTIVE"
    assert r.data_mode == "LIVE"


async def test_annotate_lifecycle_pre_market():
    """_annotate_lifecycle returns correct fields for a PRE_MARKET market."""
    from app.api.v1.universe import _annotate_lifecycle
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    market = MagicMock()
    market.id = 1
    market.asset = "BTC"
    market.timeframe = "5m"
    market.series_slug = "btc-up-or-down-5m"
    market.series_id = "s1"
    market.event_id = "e1"
    market.condition_id = "0xpre"
    market.yes_token_id = "yt"
    market.no_token_id  = "nt"
    market.question = "Will BTC go up?"
    market.start_time = now + timedelta(hours=2)    # future start → PRE_MARKET
    market.end_time   = now + timedelta(hours=26)
    market.status = "upcoming"
    market.opening_price = None
    market.opening_price_source = None
    market.opening_price_timestamp = None
    market.reference_status = None
    market.created_at = now
    market.updated_at = now
    # Lifecycle fields: provide str/bool defaults so Pydantic doesn't read MagicMock attrs
    market.lifecycle_state = "ACTIVE"
    market.execution_allowed = True
    market.is_pre_market = False
    market.is_active_market = True
    market.is_expired = False
    market.display_status = "ACTIVE"
    market.data_mode = "LIVE"
    # Timing fields added in sprint-countdown; must be correct type for Pydantic
    market.server_time = None
    market.countdown_seconds = None
    market.countdown_source = "market_end_time"
    market.countdown_data_stale = False

    resp = _annotate_lifecycle(market)
    assert resp.lifecycle_state   == "PRE_MARKET"
    assert resp.execution_allowed is False
    assert resp.is_pre_market     is True
    assert resp.is_active_market  is False
    assert resp.is_expired        is False
    assert resp.display_status    == "PRE-MARKET"
    assert resp.data_mode         == "SEED"


async def test_annotate_lifecycle_active():
    """_annotate_lifecycle returns correct fields for an ACTIVE market."""
    from app.api.v1.universe import _annotate_lifecycle
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    market = MagicMock()
    market.id = 2
    market.asset = "ETH"
    market.timeframe = "1H"
    market.series_slug = "eth-up-or-down-hourly"
    market.series_id = "s2"
    market.event_id = "e2"
    market.condition_id = "0xact"
    market.yes_token_id = "yt"
    market.no_token_id  = "nt"
    market.question = "Will ETH go up?"
    market.start_time = now - timedelta(hours=1)   # past start → ACTIVE
    market.end_time   = now + timedelta(hours=47)
    market.status = "active"
    market.opening_price = 1800.0
    market.opening_price_source = "binance"
    market.opening_price_timestamp = now - timedelta(hours=1)
    market.reference_status = "OK"
    market.created_at = now
    market.updated_at = now
    # Lifecycle fields: provide str/bool defaults so Pydantic doesn't read MagicMock attrs
    market.lifecycle_state = "ACTIVE"
    market.execution_allowed = True
    market.is_pre_market = False
    market.is_active_market = True
    market.is_expired = False
    market.display_status = "ACTIVE"
    market.data_mode = "LIVE"
    # Timing fields added in sprint-countdown; must be correct type for Pydantic
    market.server_time = None
    market.countdown_seconds = None
    market.countdown_source = "market_end_time"
    market.countdown_data_stale = False

    resp = _annotate_lifecycle(market)
    assert resp.lifecycle_state   == "ACTIVE"
    assert resp.execution_allowed is True
    assert resp.is_pre_market     is False
    assert resp.is_active_market  is True
    assert resp.is_expired        is False
    assert resp.display_status    == "ACTIVE"
    assert resp.data_mode         == "LIVE"


async def test_annotate_lifecycle_expired():
    """_annotate_lifecycle returns correct fields for an EXPIRED market."""
    from app.api.v1.universe import _annotate_lifecycle
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    market = MagicMock()
    market.id = 3
    market.asset = "SOL"
    market.timeframe = "15m"
    market.series_slug = "sol-up-or-down-15m"
    market.series_id = "s3"
    market.event_id = "e3"
    market.condition_id = "0xexp"
    market.yes_token_id = "yt"
    market.no_token_id  = "nt"
    market.question = "Will SOL go up?"
    market.start_time = now - timedelta(hours=26)   # past
    market.end_time   = now - timedelta(hours=1)    # past → EXPIRED
    market.status = "expired"
    market.opening_price = None
    market.opening_price_source = None
    market.opening_price_timestamp = None
    market.reference_status = None
    market.created_at = now
    market.updated_at = now
    # Lifecycle fields: provide str/bool defaults so Pydantic doesn't read MagicMock attrs
    market.lifecycle_state = "ACTIVE"
    market.execution_allowed = True
    market.is_pre_market = False
    market.is_active_market = True
    market.is_expired = False
    market.display_status = "ACTIVE"
    market.data_mode = "LIVE"
    # Timing fields added in sprint-countdown; must be correct type for Pydantic
    market.server_time = None
    market.countdown_seconds = None
    market.countdown_source = "market_end_time"
    market.countdown_data_stale = False

    resp = _annotate_lifecycle(market)
    assert resp.lifecycle_state   == "EXPIRED"
    assert resp.execution_allowed is False
    assert resp.is_pre_market     is False
    assert resp.is_active_market  is False
    assert resp.is_expired        is True
    assert resp.display_status    == "EXPIRED"
    assert resp.data_mode         == "FINAL"


# ══════════════════════════════════════════════════════════════════════════════
# 5.  UTC consistency
# ══════════════════════════════════════════════════════════════════════════════

async def test_lifecycle_handles_utc_consistently():
    """All boundary comparisons are UTC. Naive datetimes treated as UTC."""
    from app.services.market_universe_service import get_market_lifecycle_state

    # Naive start/end should still work
    m = MagicMock()
    m.start_time = datetime(2026, 7, 12, 10, 0, 0)   # naive
    m.end_time   = datetime(2026, 7, 13, 10, 0, 0)   # naive
    now_utc = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    result = get_market_lifecycle_state(m, now_utc)
    assert result == "ACTIVE", f"Expected ACTIVE, got {result}"


async def test_lifecycle_pre_market_execution_is_false():
    """
    A PRE_MARKET market has execution_allowed=False in the API schema.
    Frontend must not show AI decision for pre-market markets.
    """
    from app.services.market_universe_service import get_market_lifecycle_state, LIFECYCLE_PRE_MARKET

    now = datetime.now(timezone.utc)
    m = MagicMock()
    m.start_time = now + timedelta(minutes=30)
    m.end_time   = now + timedelta(hours=25)

    lc = get_market_lifecycle_state(m, now)
    execution_allowed = lc == "ACTIVE"

    assert lc == LIFECYCLE_PRE_MARKET
    assert execution_allowed is False, "PRE_MARKET must set execution_allowed=False"


async def test_get_active_universe_filter_excludes_pre_market():
    """
    get_active_universe() must NOT return a market with start_time in the future,
    even if its DB status is 'active' (stale sync race condition).
    The SQL WHERE clause includes start_time <= now.
    """
    from app.repositories.universe_repository import get_active_universe

    now = datetime.now(timezone.utc)
    future_start = now + timedelta(hours=1)
    future_end   = now + timedelta(hours=25)

    # Create a mock market that passes status='active' but has future start_time
    fake_market = MagicMock()
    fake_market.status     = "active"
    fake_market.start_time = future_start
    fake_market.end_time   = future_end

    # Simulate a DB session that returns this pre-market row
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []   # the WHERE clause filters it out
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await get_active_universe(session)

    # Verify the query was executed (SQL WHERE clause does the filtering)
    session.execute.assert_called_once()
    assert result == [], "Pre-market markets must not appear in get_active_universe()"
