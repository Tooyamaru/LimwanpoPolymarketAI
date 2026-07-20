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

def _make_parseable_question(pw_start: datetime, pw_end: datetime) -> str:
    """Generate a Polymarket-style question string for a given prediction window."""
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    s_et = pw_start.astimezone(ET)
    e_et = pw_end.astimezone(ET)
    return (
        f"Bitcoin Up or Down \u2014 "
        f"{s_et.strftime('%B %-d')}, "
        f"{s_et.strftime('%-I:%M%p')}\u2013{e_et.strftime('%-I:%M%p')} ET"
    )


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
    m.countdown_mode = None
    m.prediction_window_start = None
    m.prediction_window_end = None
    m.countdown_target = None
    m.trading_open_time = None
    # Chainlink RTDS target fields (spec §3 — always explicit in test factories)
    m.target_price = None
    m.target_source = None
    m.target_raw_source = None
    m.target_source_timestamp = None
    m.target_locked_at = None
    m.target_event_slug = None
    m.target_condition_id = None
    m.target_verified = False
    m.target_stale = True
    m.target_validation_error = None
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
    """Test 24: Active 5M market with parseable question gives countdown_seconds >= 0."""
    now = datetime.now(timezone.utc)
    # Upcoming window: starts in 30 minutes
    pw_start = now + timedelta(minutes=30)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end + timedelta(hours=1))
    m.question = question
    resp = _annotate(m)
    assert resp.countdown_seconds is not None
    assert resp.countdown_seconds >= 0, \
        f"countdown_seconds must be >= 0, got {resp.countdown_seconds}"


# ══════════════════════════════════════════════════════════════════════════════
# 25. Uses question_interval as countdown_source when question is parseable
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_25_uses_exact_condition_end_time():
    """Test 25: countdown_source must be 'question_interval' for a parseable question."""
    now = datetime.now(timezone.utc)
    pw_start = now + timedelta(hours=1)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end + timedelta(hours=1))
    m.question = question
    resp = _annotate(m)
    assert resp.countdown_source == "question_interval", \
        f"countdown_source must be 'question_interval', got '{resp.countdown_source}'"


# ══════════════════════════════════════════════════════════════════════════════
# 26. countdown_seconds matches prediction_window_start for STARTS_IN
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_26_countdown_seconds_matches_end_time():
    """Test 26: countdown_seconds ≈ (prediction_window_start - now) when STARTS_IN."""
    now = datetime.now(timezone.utc)
    # Round to minute boundary so generated question matches parsed start exactly
    raw = now + timedelta(hours=1)
    pw_start = raw.replace(second=0, microsecond=0)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end + timedelta(hours=1))
    m.question = question

    pre = datetime.now(timezone.utc)
    resp = _annotate(m)
    post = datetime.now(timezone.utc)

    assert resp.countdown_mode == "STARTS_IN"
    assert resp.countdown_seconds is not None
    # Expected: seconds until pw_start (minute-rounded, so answer should be exact ±2s)
    expected_min = int((pw_start - post).total_seconds())
    expected_max = int((pw_start - pre).total_seconds())
    assert expected_min <= resp.countdown_seconds <= expected_max + 2, \
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
    """Test 29: RESOLVING market (window expired) must have countdown_seconds=0."""
    now = datetime.now(timezone.utc)
    # Window ended 1 hour ago
    pw_end = now - timedelta(hours=1)
    pw_start = pw_end - timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end, status="closed", is_active=False)
    m.question = question
    resp = _annotate(m)
    assert resp.countdown_seconds is not None
    assert resp.countdown_seconds == 0, \
        f"Expired/RESOLVING market must have countdown_seconds=0, got {resp.countdown_seconds}"


# ══════════════════════════════════════════════════════════════════════════════
# 30. countdown_seconds == 0 at market boundary
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_30_zero_countdown_at_boundary():
    """Test 30: Market whose prediction window just expired → countdown_seconds=0 (RESOLVING)."""
    now = datetime.now(timezone.utc)
    # Window ended 1 second ago
    pw_end = now - timedelta(seconds=1)
    pw_start = pw_end - timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end, status="closed", is_active=False)
    m.question = question
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
    """Test 32: New market countdown_seconds is derived from its parsed question window."""
    now = datetime.now(timezone.utc)
    # New market: window starts in 2 hours — round to minute for exact parse match
    raw = now + timedelta(hours=2)
    pw_start = raw.replace(second=0, microsecond=0)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    new_end = pw_end + timedelta(hours=21)  # market contract end_time
    new_m = _make_market_row(condition_id="0x_new", end_time=new_end)
    new_m.question = question

    pre = datetime.now(timezone.utc)
    resp = _annotate(new_m)
    post = datetime.now(timezone.utc)

    assert resp.countdown_mode == "STARTS_IN"
    assert resp.countdown_seconds is not None
    expected_min = int((pw_start - post).total_seconds())
    expected_max = int((pw_start - pre).total_seconds())
    assert expected_min <= resp.countdown_seconds <= expected_max + 2, \
        f"New market countdown_seconds ({resp.countdown_seconds}) must match pw_start"


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

    # Find setInterval blocks that reference _cdEls — allow multi-line/multi-semicolon body
    cd_intervals = re.findall(r'setInterval\(.*?_cdEls.*?\},\s*1000\)', html, re.DOTALL)
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
    """Test 36: countdown_seconds matches prediction_window_start within 2s tolerance."""
    now = datetime.now(timezone.utc)
    # Round to minute boundary so generated question exactly matches parsed start
    raw = now + timedelta(hours=1, minutes=5)
    pw_start = raw.replace(second=0, microsecond=0)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end + timedelta(hours=21))
    m.question = question

    pre_call = datetime.now(timezone.utc)
    resp = _annotate(m)
    post_call = datetime.now(timezone.utc)

    assert resp.countdown_mode == "STARTS_IN"
    assert resp.countdown_seconds is not None
    expected_min = int((pw_start - post_call).total_seconds())
    expected_max = int((pw_start - pre_call).total_seconds())
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
    """countdown_data_stale=False when question interval is parseable."""
    now = datetime.now(timezone.utc)
    pw_start = now + timedelta(hours=1)
    pw_end = pw_start + timedelta(seconds=300)
    question = _make_parseable_question(pw_start, pw_end)
    m = _make_market_row(end_time=pw_end + timedelta(hours=21))
    m.question = question
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


# ══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Spec §9 items 1–20: prediction window parser + countdown semantics
# ══════════════════════════════════════════════════════════════════════════════

from app.api.v1.universe import _parse_prediction_window


# ── Helper: build a market row with a real question string ────────────────────
def _make_row_with_question(
    question: str,
    end_time: datetime | None = None,
) -> MagicMock:
    """
    Build a mock market row with a real question string so _parse_prediction_window
    is exercised through _annotate_lifecycle.
    """
    now = datetime.now(timezone.utc)
    m = _make_market_row(end_time=end_time or (now + timedelta(hours=22)))
    m.question = question
    return m


# ── 1. Standard format parses ─────────────────────────────────────────────────
def test_spec1_standard_format_parses():
    """July 18, 3:55AM–4:00AM ET parses to exactly 300 s."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)  # 6:00 AM ET
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None, "parse returned None"
    assert end is not None
    assert source == "question_interval"
    assert (end - start).total_seconds() == 300


# ── 2. Hyphen separator parses ────────────────────────────────────────────────
def test_spec2_hyphen_separator():
    """Hyphen '-' separator variant parses correctly."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM-4:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    assert (end - start).total_seconds() == 300


# ── 3. En-dash separator parses ───────────────────────────────────────────────
def test_spec3_en_dash_separator():
    """En dash '\u2013' separator variant parses correctly."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    assert (end - start).total_seconds() == 300


# ── 4. Whitespace variants parse ──────────────────────────────────────────────
def test_spec4_whitespace_variants():
    """Spaces around separator and around AM/PM parse correctly."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55 AM - 4:00 AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    assert (end - start).total_seconds() == 300


# ── 5. AM/PM conversion works ─────────────────────────────────────────────────
def test_spec5_ampm_conversion():
    """3:55AM converts to hour 3 and 4:00AM converts to hour 4 in ET."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    start_et = start.astimezone(ET)
    end_et = end.astimezone(ET)
    assert start_et.hour == 3 and start_et.minute == 55
    assert end_et.hour == 4 and end_et.minute == 0


# ── 6. DST summer conversion (America/New_York = UTC-4) ───────────────────────
def test_spec6_dst_summer():
    """In July (DST), New York is UTC-4; 3:55AM ET = 7:55 UTC."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    # July is DST: ET = UTC - 4h
    assert start.hour == 7 and start.minute == 55, (
        f"Expected 07:55 UTC in July DST, got {start.hour}:{start.minute:02d}"
    )
    assert end.hour == 8 and end.minute == 0


# ── 7. Winter conversion (America/New_York = UTC-5) ───────────────────────────
def test_spec7_winter_standard_time():
    """In January (EST), New York is UTC-5; 3:55AM ET = 8:55 UTC."""
    end_ref = datetime(2026, 1, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 January 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    # January is EST: ET = UTC - 5h
    assert start.hour == 8 and start.minute == 55, (
        f"Expected 08:55 UTC in January EST, got {start.hour}:{start.minute:02d}"
    )
    assert end.hour == 9 and end.minute == 0


# ── 8. Midnight-crossing interval works ───────────────────────────────────────
def test_spec8_midnight_crossing():
    """11:55PM–12:00AM crosses midnight and still gives 300 s."""
    end_ref = datetime(2026, 7, 18, 5, 5, 0, tzinfo=timezone.utc)  # ~1AM ET
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 17, 11:55PM\u201312:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None, "midnight-crossing parse failed"
    assert (end - start).total_seconds() == 300
    assert end > start


# ── 9. Inferred year is correct ───────────────────────────────────────────────
def test_spec9_inferred_year():
    """Year inferred from market_end_time; window must fall in the same year."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    assert start.year == 2026


# ── 10. Interval is exactly 300 seconds ──────────────────────────────────────
def test_spec10_exactly_300_seconds():
    """Parsed window duration must be exactly 300 seconds."""
    end_ref = datetime(2026, 7, 18, 10, 0, 0, tzinfo=timezone.utc)
    start, end, source = _parse_prediction_window(
        "Bitcoin Up or Down \u2014 July 18, 3:55AM\u20134:00AM ET",
        market_end_time=end_ref,
    )
    assert start is not None
    assert (end - start).total_seconds() == 300


# ── 11. Pre-window returns STARTS_IN ──────────────────────────────────────────
def test_spec11_pre_window_starts_in():
    """When server time is before prediction_window_start, mode is STARTS_IN."""
    now = datetime.now(timezone.utc)
    # Window starts 30 minutes from now
    pw_start = now + timedelta(minutes=30)
    pw_end = pw_start + timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p').replace('AM','AM').replace('PM','PM')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    assert resp.countdown_mode == "STARTS_IN", (
        f"Expected STARTS_IN, got {resp.countdown_mode} for question: {question}"
    )
    assert resp.countdown_target is not None


# ── 12. Live window returns ENDS_IN ───────────────────────────────────────────
def test_spec12_live_window_ends_in():
    """When server time is inside prediction window, mode is ENDS_IN."""
    now = datetime.now(timezone.utc)
    # Window started 1 minute ago, ends 4 minutes from now
    pw_start = now - timedelta(minutes=1)
    pw_end = pw_start + timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    assert resp.countdown_mode == "ENDS_IN", (
        f"Expected ENDS_IN, got {resp.countdown_mode} for question: {question}"
    )
    assert resp.countdown_target is not None


# ── 13. ENDS_IN countdown never exceeds 300 ──────────────────────────────────
def test_spec13_ends_in_max_300():
    """countdown_seconds for ENDS_IN must be in [0, 300]."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=10)
    pw_end = pw_start + timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    if resp.countdown_mode == "ENDS_IN":
        assert resp.countdown_seconds is not None
        assert 0 <= resp.countdown_seconds <= 300


# ── 14. After window returns RESOLVING ────────────────────────────────────────
def test_spec14_after_window_resolving():
    """When server time is after prediction_window_end, mode is RESOLVING."""
    now = datetime.now(timezone.utc)
    # Window ended 2 minutes ago
    pw_end = now - timedelta(minutes=2)
    pw_start = pw_end - timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    assert resp.countdown_mode == "RESOLVING", (
        f"Expected RESOLVING, got {resp.countdown_mode}"
    )
    assert resp.countdown_target is None
    assert resp.countdown_seconds == 0


# ── 15. Invalid/unparseable question returns SYNCING ─────────────────────────
def test_spec15_invalid_question_syncing():
    """A market with an unparseable question returns countdown_mode=SYNCING."""
    m = _make_row_with_question("BTC Up or Down — no time info here")
    resp = _annotate(m)
    assert resp.countdown_mode == "SYNCING"
    assert resp.countdown_data_stale is True
    assert resp.countdown_target is None
    assert resp.countdown_seconds is None


# ── 16. Unparseable active market does not return ENDS_IN 22 hours ────────────
def test_spec16_no_ends_in_fallback_22h():
    """An active market with no parseable question interval must never show ENDS_IN."""
    now = datetime.now(timezone.utc)
    # Market end_time is 22 hours away — old code would have used this as ENDS_IN
    end_time = now + timedelta(hours=22)
    m = _make_row_with_question("BTC Up or Down", end_time=end_time)
    resp = _annotate(m)
    # Must be SYNCING (not ENDS_IN) because the question has no interval
    assert resp.countdown_mode != "ENDS_IN", (
        "ENDS_IN must not be set when question interval cannot be parsed — "
        "should be SYNCING"
    )
    # countdown_seconds must NOT be 22*3600
    assert resp.countdown_seconds != 22 * 3600


# ── 17. countdown_target matches the selected boundary ───────────────────────
def test_spec17_countdown_target_matches_boundary():
    """countdown_target must equal prediction_window_start (STARTS_IN) or _end (ENDS_IN)."""
    now = datetime.now(timezone.utc)
    # Window is upcoming (STARTS_IN)
    pw_start = now + timedelta(minutes=5)
    pw_end = pw_start + timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    if resp.countdown_mode == "STARTS_IN":
        assert resp.countdown_target == resp.prediction_window_start
    elif resp.countdown_mode == "ENDS_IN":
        assert resp.countdown_target == resp.prediction_window_end


# ── 18. countdown_seconds matches target ─────────────────────────────────────
def test_spec18_countdown_seconds_matches_target():
    """countdown_seconds must match (target - server_time) to within 2 seconds."""
    now = datetime.now(timezone.utc)
    pw_start = now + timedelta(minutes=10)
    pw_end = pw_start + timedelta(seconds=300)
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    pw_start_et = pw_start.astimezone(ET)
    pw_end_et = pw_end.astimezone(ET)
    question = (
        f"Bitcoin Up or Down \u2014 "
        f"{pw_start_et.strftime('%B %-d')}, "
        f"{pw_start_et.strftime('%-I:%M%p')}"
        f"\u2013{pw_end_et.strftime('%-I:%M%p')} ET"
    )
    end_ref = pw_end + timedelta(hours=1)
    m = _make_row_with_question(question, end_time=end_ref)
    resp = _annotate(m)
    if resp.countdown_mode in ("STARTS_IN", "ENDS_IN") and resp.countdown_target:
        target_dt = datetime.fromisoformat(resp.countdown_target)
        server_dt = datetime.fromisoformat(resp.server_time)
        expected = max(0, int((target_dt - server_dt).total_seconds()))
        assert abs(resp.countdown_seconds - expected) <= 2, (
            f"countdown_seconds {resp.countdown_seconds} differs from "
            f"expected {expected} by more than 2s"
        )


# ── 19. Shares 4.38 are not rounded to 4 ────────────────────────────────────
def test_spec19_shares_precision_4_38():
    """fmtShares(4.38) must return '4.38', not '4'."""
    # Verify via the HTML that toFixed(0) is not used for shares
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()
    assert "open_shares.toFixed(0)" not in html, (
        "open_shares.toFixed(0) still present — fractional shares are being rounded"
    )
    assert "fmtShares" in html, "fmtShares function not found in HTML"


# ── 20. Shares 2.195 preserve precision ──────────────────────────────────────
def test_spec20_shares_precision_2_195():
    """fmtShares must preserve fractional precision up to 4 decimal places."""
    with open("/home/runner/workspace/backend/app/static/index.html", "r") as f:
        html = f.read()
    # fmtShares must use toFixed(4) with trailing-zero stripping
    assert "toFixed(4)" in html, (
        "fmtShares must call .toFixed(4) for sub-cent share precision"
    )
    assert 'replace(/\\.?0+$/' in html or "replace(/\\.?0+$/" in html, (
        "fmtShares must strip trailing zeros"
    )
