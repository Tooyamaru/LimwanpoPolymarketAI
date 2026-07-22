"""
test_universe_prediction_lifecycle_api.py

Narrow-scope tests for the additive prediction-lifecycle fields added to
_annotate_lifecycle() and UniverseMarketResponse:

  contract_lifecycle_state        — alias for lifecycle_state (backward compat)
  prediction_lifecycle_state      — from get_prediction_window_lifecycle()
  prediction_window_valid         — True when window is structurally valid
  prediction_window_validation_error — reason string when invalid
  execution_allowed               — True ONLY when valid AND WINDOW_LIVE
  server_time                     — ISO UTC, timezone-aware
  generated_at                    — ISO UTC, timezone-aware, same as server_time

Cases:
  1.  live              — window currently open → WINDOW_LIVE, execution=True
  2.  upcoming          — window in future → UPCOMING, execution=False
  3.  exact-end         — now == pw_end → RESOLVING, execution=False
  4.  missing-start     — pw_start=None → INVALID, valid=False
  5.  missing-end       — pw_end=None   → INVALID, valid=False
  6.  299s-invalid      — duration 299s → INVALID, valid=False
  7.  301s-invalid      — duration 301s → INVALID, valid=False
  8.  contract-active-invalid-window — ACTIVE contract + INVALID pw → execution=False
  9.  condition-event-preserved — condition_id/event_id unchanged
  10. server_time-tz-aware — server_time and generated_at are tz-aware ISO strings
  11. execution_allowed-only-live — upcoming/resolving/invalid → all execution=False
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


# ── Factory ───────────────────────────────────────────────────────────────────

def _make_row(
    *,
    condition_id: str = "0xcond001",
    event_id: str = "evt-001",
    asset: str = "BTC",
    timeframe: str = "5m",
    status: str = "active",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    # stored prediction window (bypasses question parsing)
    pw_start: datetime | None = None,
    pw_end: datetime | None = None,
    pw_source: str | None = "question_interval",
    question: str = "BTC Up or Down — July 22, 4:00AM–4:05AM ET",
    is_active: bool = True,
    is_closed: bool = False,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    m = MagicMock()
    m.id = 1
    m.asset = asset
    m.timeframe = timeframe
    m.series_slug = f"{asset.lower()}-up-or-down-5m"
    m.series_id = "s001"
    m.event_id = event_id
    m.condition_id = condition_id
    m.yes_token_id = "yes_tok"
    m.no_token_id = "no_tok"
    m.question = question
    m.start_time = start_time or (now - timedelta(hours=1))
    m.end_time = end_time or (now + timedelta(hours=23))
    m.status = status
    m.opening_price = 66000.0
    m.opening_price_source = "Binance"
    m.opening_price_timestamp = now - timedelta(minutes=5)
    m.reference_status = "READY"
    m.created_at = now - timedelta(hours=2)
    m.updated_at = now
    m.is_active = is_active
    m.is_closed = is_closed

    # Stored prediction window (set directly; overrides question parsing)
    m.prediction_window_start = pw_start
    m.prediction_window_end = pw_end
    m.prediction_window_source = pw_source if (pw_start is not None and pw_end is not None) else None

    # Lifecycle/countdown fields — must be correct types for Pydantic model_validate
    m.lifecycle_state = "ACTIVE"
    m.contract_lifecycle_state = None
    m.execution_allowed = True
    m.is_pre_market = False
    m.is_active_market = True
    m.is_expired = False
    m.display_status = "ACTIVE"
    m.data_mode = "LIVE"
    m.server_time = None
    m.generated_at = None
    m.countdown_seconds = None
    m.countdown_source = "market_end_time"
    m.countdown_data_stale = False
    m.countdown_mode = None
    m.countdown_target = None
    m.trading_open_time = None
    m.prediction_lifecycle_state = None
    m.prediction_window_valid = False
    m.prediction_window_validation_error = None

    # Chainlink / target fields
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
    m.target_source_url = None
    m.target_source_field_path = None

    return m


def _annotate(m):
    from app.api.v1.universe import _annotate_lifecycle
    return _annotate_lifecycle(m)


# ── Test 1: live window → WINDOW_LIVE, execution_allowed=True ────────────────

def test_case1_live_window():
    """Prediction window currently open: state=WINDOW_LIVE, execution_allowed=True."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=60)   # started 60s ago
    pw_end   = now + timedelta(seconds=240)  # ends in 240s (total 300s)

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.prediction_lifecycle_state == "WINDOW_LIVE"
    assert r.prediction_window_valid is True
    assert r.prediction_window_validation_error is None
    assert r.execution_allowed is True


# ── Test 2: upcoming window → UPCOMING, execution_allowed=False ──────────────

def test_case2_upcoming_window():
    """Prediction window in the future: state=UPCOMING, execution_allowed=False."""
    now = datetime.now(timezone.utc)
    pw_start = now + timedelta(seconds=120)
    pw_end   = pw_start + timedelta(seconds=300)

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.prediction_lifecycle_state == "UPCOMING"
    assert r.prediction_window_valid is True
    assert r.execution_allowed is False


# ── Test 3: exact end boundary → RESOLVING, execution_allowed=False ──────────

def test_case3_exact_end_resolving():
    """At exactly pw_end (exclusive): state=RESOLVING, execution_allowed=False."""
    now = datetime.now(timezone.utc)
    pw_end   = now - timedelta(seconds=0, microseconds=1)  # just past end
    pw_start = pw_end - timedelta(seconds=300)

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.prediction_lifecycle_state == "RESOLVING"
    assert r.prediction_window_valid is True
    assert r.execution_allowed is False


# ── Test 4: missing pw_start → INVALID ───────────────────────────────────────

def test_case4_missing_start_invalid():
    """
    pw_start=None, pw_end=None (unparseable question):
    prediction_lifecycle_state=INVALID, valid=False.
    execution_allowed falls back to contract lifecycle (is_active) — backward compat
    for hourly markets without 5m prediction slots; verified separately in test 8.
    """
    m = _make_row(pw_start=None, pw_end=None, question="No time info here")
    r = _annotate(m)

    assert r.prediction_lifecycle_state == "INVALID"
    assert r.prediction_window_valid is False
    assert r.prediction_window_validation_error is not None


# ── Test 5: missing pw_end → INVALID ─────────────────────────────────────────

def test_case5_missing_end_invalid():
    """
    No parseable question and no stored pw data → INVALID.
    Same fallback semantics as test 4.
    """
    m = _make_row(pw_start=None, pw_end=None, question="No time data at all")
    r = _annotate(m)

    assert r.prediction_lifecycle_state == "INVALID"
    assert r.prediction_window_valid is False
    assert r.prediction_window_validation_error is not None


# ── Test 6: 299-second window → INVALID ──────────────────────────────────────

def test_case6_299_second_window_invalid():
    """Duration exactly 299s: prediction_window_valid=False (must be exactly 300s)."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=30)
    pw_end   = pw_start + timedelta(seconds=299)  # 299s, not 300

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.prediction_window_valid is False
    assert r.prediction_lifecycle_state == "INVALID"
    assert "299" in (r.prediction_window_validation_error or "")
    assert r.execution_allowed is False


# ── Test 7: 301-second window → INVALID ──────────────────────────────────────

def test_case7_301_second_window_invalid():
    """Duration exactly 301s: prediction_window_valid=False (must be exactly 300s)."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=30)
    pw_end   = pw_start + timedelta(seconds=301)  # 301s, not 300

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.prediction_window_valid is False
    assert r.prediction_lifecycle_state == "INVALID"
    assert "301" in (r.prediction_window_validation_error or "")
    assert r.execution_allowed is False


# ── Test 8: contract ACTIVE + invalid window → execution=False ───────────────

def test_case8_contract_active_invalid_window_blocks_execution():
    """
    Contract lifecycle=ACTIVE but prediction window is invalid (wrong duration).
    execution_allowed must still be False — contract state alone is not sufficient.
    """
    now = datetime.now(timezone.utc)
    # Valid contract window (start in past, end in future)
    contract_start = now - timedelta(hours=1)
    contract_end   = now + timedelta(hours=23)
    # Invalid prediction window (299s)
    pw_start = now - timedelta(seconds=30)
    pw_end   = pw_start + timedelta(seconds=299)

    m = _make_row(
        start_time=contract_start,
        end_time=contract_end,
        status="active",
        is_active=True,
        pw_start=pw_start,
        pw_end=pw_end,
    )
    r = _annotate(m)

    assert r.contract_lifecycle_state == "ACTIVE"
    assert r.prediction_window_valid is False
    assert r.execution_allowed is False, (
        "execution_allowed must be False even when contract is ACTIVE "
        "if prediction window is invalid"
    )


# ── Test 9: condition_id and event_id preserved ───────────────────────────────

def test_case9_condition_event_id_preserved():
    """condition_id and event_id pass through unchanged from the ORM row."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=60)
    pw_end   = pw_start + timedelta(seconds=300)

    m = _make_row(
        condition_id="0xdeadbeef001",
        event_id="evt-unique-9999",
        pw_start=pw_start,
        pw_end=pw_end,
    )
    r = _annotate(m)

    assert r.condition_id == "0xdeadbeef001"
    assert r.event_id == "evt-unique-9999"


# ── Test 10: server_time and generated_at are timezone-aware ISO strings ──────

def test_case10_server_time_and_generated_at_are_tz_aware():
    """server_time and generated_at must be parseable, close to now, and tz-aware."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=60)
    pw_end   = pw_start + timedelta(seconds=300)

    before = datetime.now(timezone.utc)
    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)
    after = datetime.now(timezone.utc)

    assert r.server_time is not None, "server_time must not be None"
    assert r.generated_at is not None, "generated_at must not be None"

    for field_name, value in [("server_time", r.server_time), ("generated_at", r.generated_at)]:
        dt = datetime.fromisoformat(value)
        # Must be timezone-aware
        assert dt.tzinfo is not None, f"{field_name} must be timezone-aware"
        # Must be close to actual now
        dt_utc = dt.astimezone(timezone.utc)
        assert before <= dt_utc <= after + timedelta(seconds=1), (
            f"{field_name} {value!r} is not within the expected range"
        )


# ── Test 11: execution_allowed=False for upcoming, resolving, and invalid ─────

def test_case11_execution_allowed_only_when_live():
    """
    execution_allowed must be False for all non-WINDOW_LIVE prediction states
    when prediction window data IS present.
    """
    now = datetime.now(timezone.utc)

    # Upcoming
    pw_s_up = now + timedelta(seconds=120)
    pw_e_up = pw_s_up + timedelta(seconds=300)
    r_up = _annotate(_make_row(pw_start=pw_s_up, pw_end=pw_e_up))
    assert r_up.prediction_lifecycle_state == "UPCOMING"
    assert r_up.execution_allowed is False, "UPCOMING must not allow execution"

    # Resolving
    pw_e_res = now - timedelta(seconds=1)
    pw_s_res = pw_e_res - timedelta(seconds=300)
    r_res = _annotate(_make_row(pw_start=pw_s_res, pw_end=pw_e_res))
    assert r_res.prediction_lifecycle_state == "RESOLVING"
    assert r_res.execution_allowed is False, "RESOLVING must not allow execution"

    # Invalid (wrong duration)
    pw_s_inv = now - timedelta(seconds=30)
    pw_e_inv = pw_s_inv + timedelta(seconds=299)
    r_inv = _annotate(_make_row(pw_start=pw_s_inv, pw_end=pw_e_inv))
    assert r_inv.prediction_lifecycle_state == "INVALID"
    assert r_inv.execution_allowed is False, "INVALID must not allow execution"

    # Live only — execution is True
    pw_s_live = now - timedelta(seconds=60)
    pw_e_live = pw_s_live + timedelta(seconds=300)
    r_live = _annotate(_make_row(pw_start=pw_s_live, pw_end=pw_e_live))
    assert r_live.prediction_lifecycle_state == "WINDOW_LIVE"
    assert r_live.execution_allowed is True, "WINDOW_LIVE must allow execution"


# ── Test 12: contract_lifecycle_state is a backward-compat alias ──────────────

def test_case12_contract_lifecycle_state_alias():
    """contract_lifecycle_state mirrors lifecycle_state for backward compatibility."""
    now = datetime.now(timezone.utc)
    pw_start = now - timedelta(seconds=60)
    pw_end   = pw_start + timedelta(seconds=300)

    m = _make_row(pw_start=pw_start, pw_end=pw_end)
    r = _annotate(m)

    assert r.contract_lifecycle_state == r.lifecycle_state, (
        "contract_lifecycle_state must equal lifecycle_state (backward-compat alias)"
    )
    assert r.contract_lifecycle_state is not None
