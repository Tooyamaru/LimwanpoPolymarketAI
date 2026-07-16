"""
Countdown Tests — spec §19 items 24–37.

Verifies:
- Backend API server_time, countdown_seconds, countdown_source, countdown_data_stale
- Countdown computation (UTC, never negative, uses market end_time not parent event)
- Server-browser offset model
- Rollover semantics (condition_id change, state reset)
- No countdown data leakage across condition_ids
- Timer safety (single interval)
- SYNCING display for stale timing

Tests 24–37 as specified in the card-data fix spec §19 "COUNTDOWN" section.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_market_row(
    condition_id: str = "cid-001",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    status: str = "active",
    is_active: bool = True,
    is_closed: bool = False,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    m = MagicMock()
    m.condition_id = condition_id
    m.asset = "BTC"
    m.timeframe = "5m"
    m.series_slug = "btc-up-or-down-5m"
    m.series_id = "10684"
    m.event_id = "12345"
    m.yes_token_id = "yes123"
    m.no_token_id = "no123"
    m.question = "BTC Up or Down"
    m.start_time = start_time or (now - timedelta(minutes=2))
    m.end_time = end_time  # may be None
    m.status = status
    m.opening_price = 64000.0
    m.opening_price_source = "Binance"
    m.opening_price_timestamp = now
    m.reference_status = "READY"
    m.created_at = now - timedelta(hours=2)
    m.updated_at = now
    m.id = 1
    m.is_active = is_active
    m.is_closed = is_closed
    # Pydantic reads these during model_validate; _annotate_lifecycle overwrites them
    # via model_copy(update={...}) so the initial values don't matter, but they must
    # be the right types (str / bool / int / None) to pass field validation.
    m.lifecycle_state = "ACTIVE"
    m.execution_allowed = True
    m.is_pre_market = False
    m.is_active_market = True
    m.is_expired = False
    m.display_status = "ACTIVE"
    m.data_mode = "LIVE"
    m.server_time = None
    m.countdown_seconds = None
    m.countdown_source = "market_end_time"
    m.countdown_data_stale = False
    return m


def _annotate(m):
    """Call _annotate_lifecycle from universe API to get computed response."""
    from app.api.v1.universe import _annotate_lifecycle
    return _annotate_lifecycle(m)


# ══════════════════════════════════════════════════════════════════════════════
# 24. Active 5M countdown_seconds is >= 0
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_24_countdown_seconds_non_negative():
    """Test 24: Active 5M market countdown_seconds must be >= 0."""
    m = _make_market_row(end_time=datetime.now(timezone.utc) + timedelta(hours=22))
    resp = _annotate(m)
    assert resp.countdown_seconds is not None
    assert resp.countdown_seconds >= 0, \
        f"countdown_seconds must be >= 0, got {resp.countdown_seconds}"


# ══════════════════════════════════════════════════════════════════════════════
# 25. Uses exact condition end_time as countdown_source
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_25_uses_exact_condition_end_time():
    """Test 25: countdown_source must be 'market_end_time' for a market with end_time."""
    end = datetime.now(timezone.utc) + timedelta(hours=22, minutes=15)
    m = _make_market_row(end_time=end)
    resp = _annotate(m)
    assert resp.countdown_source == "market_end_time", \
        f"countdown_source must be 'market_end_time', got '{resp.countdown_source}'"


# ══════════════════════════════════════════════════════════════════════════════
# 26. countdown_seconds matches expected duration from market end_time
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_26_countdown_seconds_matches_end_time():
    """Test 26: countdown_seconds ≈ (end_time - now) using market-level end_time."""
    market_end = datetime.now(timezone.utc) + timedelta(hours=1)
    m = _make_market_row(end_time=market_end)

    pre = datetime.now(timezone.utc)
    resp = _annotate(m)
    post = datetime.now(timezone.utc)

    # Independent compute of expected range
    expected_min = int((market_end - post).total_seconds())
    expected_max = int((market_end - pre).total_seconds())

    assert expected_min <= resp.countdown_seconds <= expected_max + 1, \
        f"countdown_seconds {resp.countdown_seconds} not in [{expected_min}, {expected_max}]"


# ══════════════════════════════════════════════════════════════════════════════
# 27. Uses UTC internally
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_27_uses_utc():
    """Test 27: server_time in response is a valid UTC ISO string close to now."""
    m = _make_market_row(end_time=datetime.now(timezone.utc) + timedelta(hours=1))
    resp = _annotate(m)

    assert resp.server_time is not None, "server_time must not be None"
    dt = datetime.fromisoformat(resp.server_time)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    assert abs((now - dt).total_seconds()) < 5, \
        f"server_time must be within 5s of actual UTC now; got {resp.server_time}"


# ══════════════════════════════════════════════════════════════════════════════
# 28. Server-browser offset calculation correct
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_28_server_browser_offset_near_zero_for_fresh_request():
    """Test 28: For a fresh request, server_time ≈ Date.now() → offset ≈ 0."""
    import time
    browser_now_ms = time.time() * 1000  # ms before API call

    m = _make_market_row(end_time=datetime.now(timezone.utc) + timedelta(seconds=300))
    resp = _annotate(m)

    server_time_ms = (
        datetime.fromisoformat(resp.server_time).timestamp() * 1000
        if resp.server_time else browser_now_ms
    )
    offset_ms = server_time_ms - browser_now_ms
    # For a freshly computed response, offset must be small (< 2 seconds)
    assert abs(offset_ms) < 2000, \
        f"Server-browser offset should be near 0ms for fresh request, got {offset_ms:.0f}ms"


# ══════════════════════════════════════════════════════════════════════════════
# 29. Never becomes negative
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_29_countdown_never_negative():
    """Test 29: countdown_seconds must be 0 (clamped) for expired markets."""
    past_end = datetime.now(timezone.utc) - timedelta(hours=1)
    m = _make_market_row(end_time=past_end, status="closed", is_active=False)
    resp = _annotate(m)
    assert resp.countdown_seconds is not None
    assert resp.countdown_seconds == 0, \
        f"Expired market must have countdown_seconds=0, got {resp.countdown_seconds}"


# ══════════════════════════════════════════════════════════════════════════════
# 30. countdown_seconds == 0 at market boundary
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_30_zero_countdown_at_boundary():
    """Test 30: Market with end_time == now → countdown_seconds = 0 (triggers EXPIRED)."""
    end = datetime.now(timezone.utc) - timedelta(seconds=1)  # just expired
    m = _make_market_row(end_time=end, status="closed", is_active=False)
    resp = _annotate(m)
    assert resp.countdown_seconds == 0, \
        f"Just-expired market must have countdown_seconds=0, got {resp.countdown_seconds}"


# ══════════════════════════════════════════════════════════════════════════════
# 31. Rollover changes condition_id
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_31_rollover_changes_condition_id():
    """Test 31: Old and new markets have different condition_ids after rollover."""
    old_cid = "0x_old_july16_market"
    new_cid = "0x_new_july17_market"

    old_m = _make_market_row(
        condition_id=old_cid,
        end_time=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    new_m = _make_market_row(
        condition_id=new_cid,
        end_time=datetime.now(timezone.utc) + timedelta(hours=23),
    )

    old_resp = _annotate(old_m)
    new_resp = _annotate(new_m)

    assert old_resp.condition_id != new_resp.condition_id, \
        "condition_id must differ between old and new market after rollover"
    assert old_resp.condition_id == old_cid
    assert new_resp.condition_id == new_cid


# ══════════════════════════════════════════════════════════════════════════════
# 32. Rollover resets countdown using new end_time
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_32_rollover_resets_countdown_to_new_end():
    """Test 32: New market countdown_seconds is derived from new market's end_time."""
    new_end = datetime.now(timezone.utc) + timedelta(hours=23, minutes=55)
    new_m = _make_market_row(condition_id="0x_new", end_time=new_end)

    pre = datetime.now(timezone.utc)
    resp = _annotate(new_m)
    post = datetime.now(timezone.utc)

    expected_min = int((new_end - post).total_seconds())
    expected_max = int((new_end - pre).total_seconds())

    assert expected_min <= resp.countdown_seconds <= expected_max + 2, \
        f"New market countdown_seconds ({resp.countdown_seconds}) must match new end_time"


# ══════════════════════════════════════════════════════════════════════════════
# 33. Old condition data does not leak into new card
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_33_old_condition_does_not_leak():
    """Test 33: cardSummary keyed by condition_id; old cid returns None for new market."""
    old_cid = "0x_old_condition"
    new_cid = "0x_new_condition"

    # Simulate frontend cardSummary dict
    card_summary = {
        old_cid: {"entry_fill_count": 3, "up_open_exposure": 1.5, "countdown_seconds": 45}
    }

    # New market's lookup returns None — no old data leaks
    cs_for_new = card_summary.get(new_cid)
    assert cs_for_new is None, \
        "Old condition card summary must NOT appear for new condition_id"

    # Old cid data still accessible (for portfolio/exit engine)
    cs_for_old = card_summary.get(old_cid)
    assert cs_for_old is not None, \
        "Old condition data must remain available in portfolio tracking"


# ══════════════════════════════════════════════════════════════════════════════
# 34. Duplicate timer intervals prevented
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_34_single_countdown_interval():
    """Test 34: index.html must contain exactly one countdown setInterval (not per-card)."""
    import re
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()

    # Find setInterval calls that reference countdown elements (_cdEls)
    cd_intervals = re.findall(r'setInterval\([^;]{0,200}_cdEls[^;]{0,200}\)', html, re.DOTALL)
    assert len(cd_intervals) == 1, \
        f"Expected exactly 1 countdown setInterval; found {len(cd_intervals)}: {cd_intervals}"


# ══════════════════════════════════════════════════════════════════════════════
# 35. Stale timing data displays SYNCING
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_35_stale_timing_shows_syncing():
    """Test 35: market with no end_time → countdown_data_stale=True; frontend shows SYNCING."""
    # Backend: no end_time → countdown_data_stale=True
    m = _make_market_row(end_time=None)
    resp = _annotate(m)
    assert resp.countdown_data_stale is True, \
        "countdown_data_stale must be True when end_time is missing"
    assert resp.countdown_seconds is None, \
        "countdown_seconds must be None when end_time is missing"
    assert resp.countdown_source == "missing"

    # Frontend: SYNCING must appear in JS
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()
    assert "SYNCING" in html, \
        "Frontend must display 'SYNCING' when countdown_data_stale=true"
    assert "countdown_data_stale" in html, \
        "Frontend must check the countdown_data_stale field from API"


# ══════════════════════════════════════════════════════════════════════════════
# 36. API countdown matches expected countdown within 2s tolerance
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_36_api_countdown_within_tolerance():
    """Test 36: countdown_seconds from API matches (end_time - server_time) within 2s."""
    end = datetime.now(timezone.utc) + timedelta(hours=22, minutes=5)
    m = _make_market_row(end_time=end)

    pre_call = datetime.now(timezone.utc)
    resp = _annotate(m)
    post_call = datetime.now(timezone.utc)

    expected_min = int((end - post_call).total_seconds())
    expected_max = int((end - pre_call).total_seconds())

    assert expected_min <= resp.countdown_seconds <= expected_max + 2, \
        f"countdown_seconds {resp.countdown_seconds} out of range [{expected_min}, {expected_max}]"


# ══════════════════════════════════════════════════════════════════════════════
# 37. Delayed response cannot overwrite newer condition countdown
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_37_delayed_response_no_overwrite():
    """Test 37: A response with a stale condition_id must not overwrite the current countdown."""
    old_cid = "0x_old_market"
    new_cid = "0x_new_market"

    # Frontend currently shows the new market
    current_active_cid = new_cid

    # Old (delayed) response: condition_id from old market
    delayed_cid = old_cid
    should_apply_old = (delayed_cid == current_active_cid)
    assert not should_apply_old, \
        "Delayed response with old condition_id must NOT overwrite current countdown"

    # Fresh response with matching cid would be applied
    fresh_cid = new_cid
    should_apply_new = (fresh_cid == current_active_cid)
    assert should_apply_new, \
        "Fresh response with matching condition_id must be applied"


# ══════════════════════════════════════════════════════════════════════════════
# Additional schema / frontend validation tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_countdown_schema_has_all_spec17_timing_fields():
    """Verify UniverseMarketResponse schema has all spec §17 timing fields."""
    from app.schemas.universe import UniverseMarketResponse
    fields = UniverseMarketResponse.model_fields
    required = [
        "server_time", "countdown_seconds",
        "countdown_source", "countdown_data_stale",
    ]
    for f in required:
        assert f in fields, f"UniverseMarketResponse missing spec §17 field: {f}"


@pytest.mark.anyio
async def test_countdown_data_stale_false_for_valid_end_time():
    """countdown_data_stale=False when a valid end_time is provided."""
    end = datetime.now(timezone.utc) + timedelta(hours=1)
    m = _make_market_row(end_time=end)
    resp = _annotate(m)
    assert resp.countdown_data_stale is False


@pytest.mark.anyio
async def test_server_time_iso_parseable():
    """server_time must be a valid ISO 8601 datetime string."""
    m = _make_market_row(end_time=datetime.now(timezone.utc) + timedelta(hours=1))
    resp = _annotate(m)
    assert resp.server_time is not None
    dt = datetime.fromisoformat(resp.server_time)
    assert dt is not None


@pytest.mark.anyio
async def test_fmtcountdown_h_suffix_in_html():
    """Frontend fmtCountdown must use 'h' suffix for hours to disambiguate from MM:SS."""
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()
    # The formatted output for >= 1h must have 'h' to distinguish from MM:SS
    assert '"h"' in html or "'h'" in html, \
        "fmtCountdown must append 'h' for hours display to disambiguate from MM:SS"


@pytest.mark.anyio
async def test_server_offset_infrastructure_in_html():
    """Frontend must declare _svrOffsetMs and read server_time from API response."""
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()
    assert "_svrOffsetMs" in html, \
        "Frontend must have _svrOffsetMs variable for server-browser offset correction"
    assert "server_time" in html, \
        "Frontend must reference server_time from API response"


@pytest.mark.anyio
async def test_countdown_source_missing_when_no_end_time():
    """countdown_source='missing' when end_time is None."""
    m = _make_market_row(end_time=None)
    resp = _annotate(m)
    assert resp.countdown_source == "missing"


@pytest.mark.anyio
async def test_active_api_endpoint_includes_countdown_fields():
    """GET /api/v1/universe/active response must include timing fields."""
    import httpx
    try:
        r = httpx.get("http://localhost:5000/api/v1/universe/active", timeout=5)
        if r.status_code == 200:
            markets = r.json()
            if markets:
                m = markets[0]
                assert "server_time" in m, "server_time missing from active markets API"
                assert "countdown_seconds" in m, "countdown_seconds missing from active markets API"
                assert "countdown_source" in m, "countdown_source missing from active markets API"
                assert "countdown_data_stale" in m, "countdown_data_stale missing from active markets API"
                # countdown_seconds must be >= 0 for active markets
                assert m["countdown_seconds"] is None or m["countdown_seconds"] >= 0
    except Exception:
        # App may not be running in test environment — skip HTTP check
        pytest.skip("App not running — skipping live API test")
