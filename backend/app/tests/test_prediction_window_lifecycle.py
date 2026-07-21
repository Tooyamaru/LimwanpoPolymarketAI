"""
test_prediction_window_lifecycle.py — canonical prediction-window lifecycle tests.

All datetimes are fixed, timezone-aware UTC values.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.prediction_window import (
    PRED_INVALID,
    PRED_RESOLVED,
    PRED_RESOLVING,
    PRED_WINDOW_LIVE,
    PRED_WINDOW_UPCOMING,
    get_prediction_window_lifecycle,
)

# Fixed anchor: a clean 5-minute-aligned UTC slot
START = datetime(2026, 7, 21, 6, 0, 0, tzinfo=timezone.utc)
END = START + timedelta(seconds=300)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call(now, resolved=False, metadata_valid=True, start=START, end=END):
    return get_prediction_window_lifecycle(
        prediction_window_start=start,
        prediction_window_end=end,
        now=now,
        resolved=resolved,
        metadata_valid=metadata_valid,
    )


# ---------------------------------------------------------------------------
# State tests
# ---------------------------------------------------------------------------

def test_upcoming():
    now = START - timedelta(seconds=1)
    result = _call(now)
    assert result["state"] == PRED_WINDOW_UPCOMING
    assert result["valid"] is True
    assert result["validation_error"] is None


def test_exact_start_is_window_live():
    result = _call(START)
    assert result["state"] == PRED_WINDOW_LIVE
    assert result["valid"] is True


def test_middle_of_window_is_window_live():
    now = START + timedelta(seconds=150)
    result = _call(now)
    assert result["state"] == PRED_WINDOW_LIVE
    assert result["valid"] is True


def test_one_second_before_end_is_window_live():
    now = END - timedelta(seconds=1)
    result = _call(now)
    assert result["state"] == PRED_WINDOW_LIVE
    assert result["valid"] is True


def test_exact_end_is_resolving():
    result = _call(END)
    assert result["state"] == PRED_RESOLVING
    assert result["valid"] is True


def test_after_end_is_resolving():
    now = END + timedelta(seconds=60)
    result = _call(now)
    assert result["state"] == PRED_RESOLVING
    assert result["valid"] is True


def test_resolved_is_resolved():
    now = END + timedelta(seconds=10)
    result = _call(now, resolved=True)
    assert result["state"] == PRED_RESOLVED
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------

def test_missing_start_is_invalid():
    result = get_prediction_window_lifecycle(
        prediction_window_start=None,
        prediction_window_end=END,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False
    assert result["validation_error"] is not None


def test_missing_end_is_invalid():
    result = get_prediction_window_lifecycle(
        prediction_window_start=START,
        prediction_window_end=None,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_naive_start_is_invalid():
    naive_start = datetime(2026, 7, 21, 6, 0, 0)  # no tzinfo
    result = get_prediction_window_lifecycle(
        prediction_window_start=naive_start,
        prediction_window_end=END,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_naive_end_is_invalid():
    naive_end = datetime(2026, 7, 21, 6, 5, 0)  # no tzinfo
    result = get_prediction_window_lifecycle(
        prediction_window_start=START,
        prediction_window_end=naive_end,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_end_before_start_is_invalid():
    result = get_prediction_window_lifecycle(
        prediction_window_start=END,
        prediction_window_end=START,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_end_equal_start_is_invalid():
    result = get_prediction_window_lifecycle(
        prediction_window_start=START,
        prediction_window_end=START,
        now=START,
    )
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_duration_299_is_invalid():
    result = _call(START, start=START, end=START + timedelta(seconds=299))
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_duration_301_is_invalid():
    result = _call(START, start=START, end=START + timedelta(seconds=301))
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


def test_metadata_invalid_is_invalid():
    result = _call(START, metadata_valid=False)
    assert result["state"] == PRED_INVALID
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# Timing field tests
# ---------------------------------------------------------------------------

def test_seconds_to_start_correct():
    now = START - timedelta(seconds=42)
    result = _call(now)
    assert result["seconds_to_start"] == 42


def test_seconds_to_end_correct():
    now = START + timedelta(seconds=100)
    result = _call(now)
    assert result["seconds_to_end"] == 200
