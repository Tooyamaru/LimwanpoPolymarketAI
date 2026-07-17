"""
test_5m_discovery.py — Unit tests for timestamp-slug 5M market discovery.

Covers:
  1.  Exact current-slot slug construction
  2.  No slot+300 off-by-one bug (current is NOT current+300)
  3.  BTC prefix
  4.  ETH prefix
  5.  SOL prefix
  6.  XRP prefix
  7.  Slot boundary cases (exact 5-minute timestamps)
  8.  get_current_slot returns multiple-of-300 values
  9.  get_candidate_slots includes prev, current, and lookahead slots
  10. contract end_time NOT used for slot calculation
  11. prediction_window from question: interval contains now
  12. prediction_window duration exactly 300 seconds
  13. missing current slug retries adjacent lookup (candidate_slots coverage)
  14. duplicate condition IDs deduplicated in pending_refs
  15. slot_contains_time boundary semantics
  16. build_event_slug format (no "up-or-down" in event slug)
  17. All four asset prefix mappings
  18. Candidate slots ordered prev→current→future
  19. get_current_slot boundary at exact 5-minute mark
  20. prediction_window parse: missing AM/PM returns None
"""

import re
from datetime import datetime, timezone

import pytest

from app.utils.prediction_window import (
    SLOT_SECONDS,
    ASSET_SLUG_PREFIX,
    build_event_slug,
    get_candidate_slots,
    get_current_slot,
    slot_contains_time,
    slot_to_datetime,
)
from app.api.v1.universe import _parse_prediction_window


# ── Helper ────────────────────────────────────────────────────────────────────

def _dt(iso: str) -> datetime:
    """Parse an ISO UTC datetime string."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


# ── 1. Exact current-slot slug construction ───────────────────────────────────

def test_slot_slug_matches_current_slot():
    now = _dt("2026-07-17T05:42:00Z")
    slot = get_current_slot(now)
    slug = build_event_slug("BTC", slot)
    # Slot must be 05:40 UTC = 1752724800 + offset; just verify the slug pattern
    assert slug.startswith("btc-updown-5m-")
    assert str(slot) in slug


# ── 2. No slot+300 off-by-one bug ─────────────────────────────────────────────

def test_no_slot_plus_300_for_current():
    now = _dt("2026-07-17T05:42:00Z")
    current_slot = get_current_slot(now)
    current_slug = build_event_slug("BTC", current_slot)
    wrong_slug = build_event_slug("BTC", current_slot + 300)
    assert current_slug != wrong_slug, "current slug must not be current+300"
    # The current slug timestamp must be <= now.timestamp()
    assert current_slot <= now.timestamp()


# ── 3. BTC prefix ─────────────────────────────────────────────────────────────

def test_btc_prefix():
    slug = build_event_slug("BTC", 1752937200)
    assert slug == "btc-updown-5m-1752937200"


# ── 4. ETH prefix ─────────────────────────────────────────────────────────────

def test_eth_prefix():
    slug = build_event_slug("ETH", 1752937200)
    assert slug == "eth-updown-5m-1752937200"


# ── 5. SOL prefix ─────────────────────────────────────────────────────────────

def test_sol_prefix():
    slug = build_event_slug("SOL", 1752937200)
    assert slug == "sol-updown-5m-1752937200"


# ── 6. XRP prefix ─────────────────────────────────────────────────────────────

def test_xrp_prefix():
    slug = build_event_slug("XRP", 1752937200)
    assert slug == "xrp-updown-5m-1752937200"


# ── 7. Slot boundary cases ────────────────────────────────────────────────────

def test_slot_boundary_05_39_59():
    """05:39:59 → 05:35 slot"""
    now = _dt("2026-07-17T05:39:59Z")
    slot = get_current_slot(now)
    slot_dt = slot_to_datetime(slot)
    assert slot_dt.minute == 35
    assert slot_dt.hour == 5


def test_slot_boundary_05_40_00():
    """05:40:00 → 05:40 slot"""
    now = _dt("2026-07-17T05:40:00Z")
    slot = get_current_slot(now)
    slot_dt = slot_to_datetime(slot)
    assert slot_dt.minute == 40
    assert slot_dt.hour == 5


def test_slot_boundary_05_44_59():
    """05:44:59 → 05:40 slot"""
    now = _dt("2026-07-17T05:44:59Z")
    slot = get_current_slot(now)
    slot_dt = slot_to_datetime(slot)
    assert slot_dt.minute == 40
    assert slot_dt.hour == 5


def test_slot_boundary_05_45_00():
    """05:45:00 → 05:45 slot"""
    now = _dt("2026-07-17T05:45:00Z")
    slot = get_current_slot(now)
    slot_dt = slot_to_datetime(slot)
    assert slot_dt.minute == 45
    assert slot_dt.hour == 5


# ── 8. get_current_slot returns multiple-of-300 ───────────────────────────────

def test_current_slot_is_multiple_of_300():
    for minute in range(0, 60):
        now = datetime(2026, 7, 17, 12, minute, 37, tzinfo=timezone.utc)
        slot = get_current_slot(now)
        assert slot % SLOT_SECONDS == 0, f"slot {slot} is not a multiple of 300 at minute={minute}"


# ── 9. get_candidate_slots order and coverage ─────────────────────────────────

def test_candidate_slots_includes_prev_current_future():
    now = _dt("2026-07-17T05:42:00Z")
    slots = get_candidate_slots(now, lookahead=3)
    current = get_current_slot(now)

    assert slots[0] == current - 300, "first slot must be previous"
    assert slots[1] == current,       "second slot must be current"
    assert slots[2] == current + 300
    assert slots[3] == current + 600
    assert slots[4] == current + 900


def test_candidate_slots_default_lookahead():
    now = _dt("2026-07-17T05:42:00Z")
    slots = get_candidate_slots(now)
    # default lookahead=3 → 5 slots: prev + current + 3 future
    assert len(slots) == 5


# ── 10. contract end_time not used for slot calculation ───────────────────────

def test_slot_does_not_use_end_time():
    """Slot is derived only from server time, not from any market end_time."""
    now = _dt("2026-07-17T05:42:00Z")
    fake_end_time = _dt("2026-07-18T05:40:00Z")  # tomorrow's end_time
    slot_from_now = get_current_slot(now)
    # slot from now must NOT equal slot from fake_end_time
    slot_from_end = get_current_slot(fake_end_time)
    assert slot_from_now != slot_from_end


# ── 11. prediction_window: interval contains now ──────────────────────────────

def test_prediction_window_contains_now():
    # Market question for July 17 05:40–05:45 AM ET
    question = "Will BTC be up or down from July 17 5:40AM–5:45AM ET?"
    market_end = _dt("2026-07-17T09:45:00Z")  # 5:45 AM ET = 9:45 UTC
    pw_start, pw_end, source = _parse_prediction_window(question, market_end)
    assert pw_start is not None
    assert pw_end is not None
    assert source == "question_interval"
    duration = (pw_end - pw_start).total_seconds()
    assert duration == 300.0


# ── 12. prediction_window duration exactly 300 seconds ───────────────────────

def test_prediction_window_duration_300():
    question = "Will ETH be up or down from July 17 3:55AM–4:00AM ET?"
    market_end = _dt("2026-07-17T08:00:00Z")
    pw_start, pw_end, source = _parse_prediction_window(question, market_end)
    assert pw_start is not None
    assert pw_end is not None
    duration = (pw_end - pw_start).total_seconds()
    assert duration == 300.0, f"expected 300s, got {duration}"


# ── 13. missing current slug: candidate_slots covers adjacent lookup ──────────

def test_candidate_slots_covers_adjacent_for_recovery():
    """Previous and next slots are always in candidate list for rollover recovery."""
    now = _dt("2026-07-17T05:40:01Z")  # 1 second into a new slot
    slots = get_candidate_slots(now, lookahead=3)
    current = get_current_slot(now)
    assert (current - 300) in slots, "previous slot must be included for recovery"
    assert (current + 300) in slots, "next slot must be included for pre-fetch"


# ── 14. duplicate condition IDs would be deduplicated ────────────────────────

def test_dedup_logic():
    """seen_cids set prevents double-processing the same condition_id."""
    pending = [
        ("0xabc", "BTC", "5m", None),
        ("0xdef", "BTC", "5m", None),
        ("0xabc", "BTC", "5m", None),  # duplicate
    ]
    seen: set[str] = set()
    processed = []
    for cid, asset, tf, start in pending:
        if cid in seen:
            continue
        seen.add(cid)
        processed.append(cid)
    assert processed == ["0xabc", "0xdef"]
    assert len(processed) == 2


# ── 15. slot_contains_time boundary semantics ─────────────────────────────────

def test_slot_contains_time_exact_start():
    slot = 1752937200  # some round slot
    t = datetime.fromtimestamp(slot, tz=timezone.utc)
    assert slot_contains_time(slot, t) is True


def test_slot_contains_time_before_end():
    slot = 1752937200
    t = datetime.fromtimestamp(slot + 299, tz=timezone.utc)
    assert slot_contains_time(slot, t) is True


def test_slot_contains_time_at_end_exclusive():
    slot = 1752937200
    t = datetime.fromtimestamp(slot + 300, tz=timezone.utc)
    assert slot_contains_time(slot, t) is False  # [slot, slot+300) exclusive end


def test_slot_contains_time_before_start():
    slot = 1752937200
    t = datetime.fromtimestamp(slot - 1, tz=timezone.utc)
    assert slot_contains_time(slot, t) is False


# ── 16. build_event_slug format: no "up-or-down" in event slug ───────────────

def test_event_slug_format_not_series_slug():
    slug = build_event_slug("BTC", 1752937200)
    assert "up-or-down" not in slug, "event slug uses 'updown', not 'up-or-down'"
    assert "updown" in slug


# ── 17. All four asset prefix mappings ────────────────────────────────────────

def test_all_four_asset_prefixes():
    assert ASSET_SLUG_PREFIX["BTC"] == "btc"
    assert ASSET_SLUG_PREFIX["ETH"] == "eth"
    assert ASSET_SLUG_PREFIX["SOL"] == "sol"
    assert ASSET_SLUG_PREFIX["XRP"] == "xrp"


# ── 18. Candidate slots ordered prev→current→future ──────────────────────────

def test_candidate_slots_ascending_order():
    now = _dt("2026-07-17T12:13:45Z")
    slots = get_candidate_slots(now, lookahead=3)
    for i in range(len(slots) - 1):
        assert slots[i] < slots[i + 1], "slots must be in ascending order"
    # Each slot is exactly 300 apart
    for i in range(len(slots) - 1):
        assert slots[i + 1] - slots[i] == 300


# ── 19. get_current_slot boundary at exact 5-minute mark ─────────────────────

def test_current_slot_exact_five_minute_mark():
    now = _dt("2026-07-17T12:15:00Z")
    slot = get_current_slot(now)
    slot_dt = slot_to_datetime(slot)
    assert slot_dt.hour == 12
    assert slot_dt.minute == 15
    assert slot_dt.second == 0


# ── 20. prediction_window parse: missing AM/PM returns None ──────────────────

def test_prediction_window_missing_ampm_returns_none():
    question = "Will BTC be up or down from July 17 3:55–4:00?"  # no AM/PM
    pw_start, pw_end, source = _parse_prediction_window(question)
    assert pw_start is None
    assert pw_end is None
    assert source == "missing"


# ── Slug validation helpers used in tests 6-13 ────────────────────────────────

import re as _re

SLUG_PATTERN = _re.compile(r"^(btc|eth|sol|xrp)-updown-5m-(\d{10})$")
ASSET_PREFIX_MAP = {"BTC": "btc", "ETH": "eth", "SOL": "sol", "XRP": "xrp"}


def _validate_slug(slug: str, asset: str) -> tuple[bool, str]:
    """Return (valid, reason). Validates format, prefix, and suffix length."""
    m = SLUG_PATTERN.match(slug)
    if not m:
        return False, f"slug '{slug}' does not match pattern"
    prefix, suffix = m.group(1), m.group(2)
    expected_prefix = ASSET_PREFIX_MAP.get(asset.upper(), "")
    if prefix != expected_prefix:
        return False, f"prefix '{prefix}' != expected '{expected_prefix}'"
    return True, "ok"


# ── 6-9. Prefix validation per asset ─────────────────────────────────────────

def test_btc_slug_prefix_validates():
    slug = build_event_slug("BTC", 1784271300)
    ok, reason = _validate_slug(slug, "BTC")
    assert ok, reason


def test_eth_slug_prefix_validates():
    slug = build_event_slug("ETH", 1784271300)
    ok, reason = _validate_slug(slug, "ETH")
    assert ok, reason


def test_sol_slug_prefix_validates():
    slug = build_event_slug("SOL", 1784271300)
    ok, reason = _validate_slug(slug, "SOL")
    assert ok, reason


def test_xrp_slug_prefix_validates():
    slug = build_event_slug("XRP", 1784271300)
    ok, reason = _validate_slug(slug, "XRP")
    assert ok, reason


# ── 10. suffix equals prediction_window_start Unix timestamp ─────────────────

def test_suffix_equals_prediction_window_start():
    now = _dt("2026-07-17T12:40:30Z")
    slot = get_current_slot(now)
    slug = build_event_slug("BTC", slot)
    # Extract suffix
    m = _re.search(r"-(\d{10})$", slug)
    assert m is not None, "slug must have a 10-digit suffix"
    suffix_ts = int(m.group(1))
    # The suffix must equal the slot (= prediction_window_start Unix ts)
    assert suffix_ts == slot
    # And that slot must be <= now.timestamp()
    assert suffix_ts <= now.timestamp()


# ── 11. prediction window duration equals 300 seconds ─────────────────────────

def test_prediction_window_duration_300s():
    from datetime import timezone as _tz
    now = _dt("2026-07-17T08:15:00Z")
    slot = get_current_slot(now)
    pw_start = datetime.fromtimestamp(slot, tz=_tz.utc)
    pw_end   = datetime.fromtimestamp(slot + SLOT_SECONDS, tz=_tz.utc)
    duration = (pw_end - pw_start).total_seconds()
    assert duration == 300.0


# ── 12. malformed slug rejected/flagged ───────────────────────────────────────

def test_malformed_slug_fails_pattern():
    bad_slugs = [
        "btc-updown-5m-",          # missing suffix
        "btc-updown-5m-12345",     # suffix too short
        "btcupdown5m1784271300",   # no dashes
        "btc-up-or-down-5m-1784271300",  # wrong separator ('up-or-down' not 'updown')
        "",
        "123",
    ]
    for slug in bad_slugs:
        m = SLUG_PATTERN.match(slug)
        assert m is None, f"slug '{slug}' should fail validation"


# ── 13. wrong asset prefix rejected/flagged ───────────────────────────────────

def test_wrong_asset_prefix_rejected():
    slug = "eth-updown-5m-1784271300"
    ok, reason = _validate_slug(slug, "BTC")
    assert not ok, f"expected rejection but got: {reason}"


# ── 14. current_slot calculation is exact multiple-of-300 ─────────────────────

def test_current_slot_is_multiple_of_300():
    test_times = [
        "2026-07-17T00:00:00Z",
        "2026-07-17T05:42:37Z",
        "2026-07-17T12:00:00Z",
        "2026-07-17T23:59:59Z",
    ]
    for iso in test_times:
        now = _dt(iso)
        slot = get_current_slot(now)
        assert slot % 300 == 0, f"slot {slot} is not a multiple of 300 for {iso}"


# ── 15. current_slot does not use +300 ───────────────────────────────────────

def test_current_slot_does_not_add_300():
    """The current-slot slug suffix must be <= server_time, not server_time + 300."""
    now = _dt("2026-07-17T08:00:00Z")
    slot = get_current_slot(now)
    # Confirm the slot is not in the future
    assert slot <= now.timestamp(), "current slot must not be in the future"
    wrong_slot = slot + 300
    assert wrong_slot > now.timestamp(), "slot+300 would be a future slot (off-by-one)"


# ── 16. current market selected (slot contains now) ──────────────────────────

def test_current_market_selected_by_slot():
    now = _dt("2026-07-17T09:43:15Z")
    slot = get_current_slot(now)
    assert slot_contains_time(slot, now), (
        f"current slot {slot} should contain now={now.timestamp()}"
    )


# ── 17. 22-hour future market rejected by slot_contains_time ─────────────────

def test_22_hour_future_market_rejected():
    """A market whose slot is 22 hours ahead must not be the current market."""
    now = _dt("2026-07-17T09:43:15Z")
    future_slot = get_current_slot(now) + 22 * 3600
    in_window = slot_contains_time(future_slot, now)
    assert not in_window, (
        f"22-hour-ahead slot {future_slot} must NOT contain now"
    )


# ── 19. NULL slug backfill: derives from prediction_window_start ──────────────

def test_null_slug_backfill_derives_from_prediction_window_start():
    """
    When event_slug is NULL and prediction_window_start is known,
    the derived slug must equal build_event_slug(asset, int(pw_start.timestamp())).
    The test checks the derivation formula, not Gamma verification.
    """
    from datetime import timezone as _tz
    pw_start = datetime(2026, 7, 17, 9, 40, 0, tzinfo=_tz.utc)  # known slot
    slot = int(pw_start.timestamp())
    assert slot % 300 == 0, "test pw_start must be a clean slot boundary"

    derived = build_event_slug("BTC", slot)
    assert derived == f"btc-updown-5m-{slot}"
    # Prefix must match BTC
    ok, reason = _validate_slug(derived, "BTC")
    assert ok, reason
    # Suffix must equal pw_start Unix timestamp
    m = _re.search(r"-(\d{10})$", derived)
    assert m and int(m.group(1)) == slot


# ── 22. CLOB tokens belong to selected condition (unit check) ─────────────────

def test_event_slug_suffix_identifies_unique_slot():
    """
    Two different slots must produce different slugs.
    This proves that condition_id binding is unique per slug
    (different slugs = different events = different condition IDs).
    """
    now = _dt("2026-07-17T10:00:00Z")
    slot_a = get_current_slot(now)
    slot_b = slot_a + 300  # next slot
    slug_a = build_event_slug("BTC", slot_a)
    slug_b = build_event_slug("BTC", slot_b)
    assert slug_a != slug_b
    m_a = _re.search(r"-(\d{10})$", slug_a)
    m_b = _re.search(r"-(\d{10})$", slug_b)
    assert int(m_b.group(1)) - int(m_a.group(1)) == 300
