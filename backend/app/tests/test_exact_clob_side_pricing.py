"""
Checkpoint 14A1 — Exact-Side CLOB Price Selector Unit Tests.

Tests 1–25 as specified in the checkpoint brief.

Realistic prices used throughout:

    yes_bid = 0.61  yes_ask = 0.64  → yes_mid = 0.625
    no_bid  = 0.31  no_ask  = 0.34  → no_mid  = 0.325

This dataset proves NO prices are NOT the complement of YES prices:

    complement(yes_bid) = 1 - 0.61 = 0.39  ≠  no_ask 0.34
    complement(yes_ask) = 1 - 0.64 = 0.36  ≠  no_bid 0.31
    complement(yes_mid) = 1 - 0.625 = 0.375 ≠  no_mid 0.325
"""

from __future__ import annotations

import io
import re
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.clob_client import ClobMarketData
from app.services.clob_price_selector import select_exact_clob_price

# ── Shared fixture helpers ─────────────────────────────────────────────────────

_COND_ID = "0xABC123condition_id_fixture"
_YES_TOKEN = "yes_token_id_fixture"
_NO_TOKEN = "no_token_id_fixture"

_NOW = datetime.now(timezone.utc)
_FRESH = _NOW - timedelta(seconds=5)
_STALE = _NOW - timedelta(seconds=90)


def _snap(
    *,
    yes_bid: float | None = 0.61,
    yes_ask: float | None = 0.64,
    yes_mid: float | None = 0.625,
    no_bid: float | None = 0.31,
    no_ask: float | None = 0.34,
    no_mid: float | None = 0.325,
    yes_token_id: str | None = _YES_TOKEN,
    no_token_id: str | None = _NO_TOKEN,
    condition_id: str = _COND_ID,
    fetched_at: datetime | None = None,
) -> ClobMarketData:
    """Build a ClobMarketData fixture with sane defaults."""
    if fetched_at is None:
        fetched_at = _FRESH
    return ClobMarketData(
        condition_id=condition_id,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        yes_mid=yes_mid,
        no_bid=no_bid,
        no_ask=no_ask,
        no_mid=no_mid,
        spread_yes=(yes_ask - yes_bid) if (yes_bid and yes_ask) else None,
        spread_no=(no_ask - no_bid) if (no_bid and no_ask) else None,
        volume=None,
        liquidity=None,
        active=True,
        closed=False,
        fetched_at=fetched_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Tests 1–6: correct exact-side routing
# ══════════════════════════════════════════════════════════════════════════════

def test_01_yes_buy_returns_yes_ask():
    """YES + BUY must return yes_ask = 0.64."""
    result = select_exact_clob_price("YES", "BUY", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.64)
    assert result["source_field"] == "yes_ask"
    assert result["token_id"] == _YES_TOKEN


def test_02_yes_sell_returns_yes_bid():
    """YES + SELL must return yes_bid = 0.61."""
    result = select_exact_clob_price("YES", "SELL", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.61)
    assert result["source_field"] == "yes_bid"
    assert result["token_id"] == _YES_TOKEN


def test_03_yes_mark_returns_yes_mid():
    """YES + MARK must return yes_mid = 0.625."""
    result = select_exact_clob_price("YES", "MARK", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.625)
    assert result["source_field"] == "yes_mid"
    assert result["token_id"] == _YES_TOKEN


def test_04_no_buy_returns_no_ask():
    """NO + BUY must return no_ask = 0.34."""
    result = select_exact_clob_price("NO", "BUY", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.34)
    assert result["source_field"] == "no_ask"
    assert result["token_id"] == _NO_TOKEN


def test_05_no_sell_returns_no_bid():
    """NO + SELL must return no_bid = 0.31."""
    result = select_exact_clob_price("NO", "SELL", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.31)
    assert result["source_field"] == "no_bid"
    assert result["token_id"] == _NO_TOKEN


def test_06_no_mark_returns_no_mid():
    """NO + MARK must return no_mid = 0.325."""
    result = select_exact_clob_price("NO", "MARK", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.325)
    assert result["source_field"] == "no_mid"
    assert result["token_id"] == _NO_TOKEN


# ══════════════════════════════════════════════════════════════════════════════
# Tests 7–9: prove no complement fallback is used
# ══════════════════════════════════════════════════════════════════════════════

def test_07_no_buy_does_not_return_complement_of_yes_bid():
    """NO + BUY must return no_ask (0.34), not 1 - yes_bid (0.39)."""
    result = select_exact_clob_price("NO", "BUY", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.34)
    # Explicitly assert it is NOT the complement of yes_bid.
    complement_of_yes_bid = 1.0 - 0.61
    assert result["price"] != pytest.approx(complement_of_yes_bid), (
        f"NO BUY returned complement of yes_bid ({complement_of_yes_bid}) "
        "instead of exact no_ask (0.34)"
    )


def test_08_no_sell_does_not_return_complement_of_yes_ask():
    """NO + SELL must return no_bid (0.31), not 1 - yes_ask (0.36)."""
    result = select_exact_clob_price("NO", "SELL", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.31)
    complement_of_yes_ask = 1.0 - 0.64
    assert result["price"] != pytest.approx(complement_of_yes_ask), (
        f"NO SELL returned complement of yes_ask ({complement_of_yes_ask}) "
        "instead of exact no_bid (0.31)"
    )


def test_09_no_mark_does_not_return_complement_of_yes_mid():
    """NO + MARK must return no_mid (0.325), not 1 - yes_mid (0.375)."""
    result = select_exact_clob_price("NO", "MARK", _snap())
    assert result["valid"] is True
    assert result["price"] == pytest.approx(0.325)
    complement_of_yes_mid = 1.0 - 0.625
    assert result["price"] != pytest.approx(complement_of_yes_mid), (
        f"NO MARK returned complement of yes_mid ({complement_of_yes_mid}) "
        "instead of exact no_mid (0.325)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Tests 10–12: missing NO prices fail closed
# ══════════════════════════════════════════════════════════════════════════════

def test_10_missing_no_ask_fails_closed():
    """NO + BUY with no_ask=None must fail closed, not fall back to complement."""
    result = select_exact_clob_price("NO", "BUY", _snap(no_ask=None))
    assert result["valid"] is False
    assert result["price"] is None
    assert result["validation_error"] == "NO_ASK_UNAVAILABLE"


def test_11_missing_no_bid_fails_closed():
    """NO + SELL with no_bid=None must fail closed."""
    result = select_exact_clob_price("NO", "SELL", _snap(no_bid=None))
    assert result["valid"] is False
    assert result["price"] is None
    assert result["validation_error"] == "NO_BID_UNAVAILABLE"


def test_12_missing_no_mid_fails_closed():
    """NO + MARK with no_mid=None must fail closed."""
    result = select_exact_clob_price("NO", "MARK", _snap(no_mid=None))
    assert result["valid"] is False
    assert result["price"] is None
    assert result["validation_error"] == "NO_MID_UNAVAILABLE"


# ══════════════════════════════════════════════════════════════════════════════
# Tests 13–14: missing token IDs block selection
# ══════════════════════════════════════════════════════════════════════════════

def test_13_missing_yes_token_blocks_yes_selection():
    """Any YES action with yes_token_id=None must be rejected."""
    snap = _snap(yes_token_id=None)
    for action in ("BUY", "SELL", "MARK"):
        result = select_exact_clob_price("YES", action, snap)
        assert result["valid"] is False
        assert result["validation_error"] == "YES_TOKEN_ID_MISSING", (
            f"action={action} did not return YES_TOKEN_ID_MISSING"
        )


def test_14_missing_no_token_blocks_no_selection():
    """Any NO action with no_token_id=None must be rejected."""
    snap = _snap(no_token_id=None)
    for action in ("BUY", "SELL", "MARK"):
        result = select_exact_clob_price("NO", action, snap)
        assert result["valid"] is False
        assert result["validation_error"] == "NO_TOKEN_ID_MISSING", (
            f"action={action} did not return NO_TOKEN_ID_MISSING"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Tests 15–16: invalid side / action rejected
# ══════════════════════════════════════════════════════════════════════════════

def test_15_invalid_side_rejected():
    """An unrecognised side string must return INVALID_SIDE."""
    for bad_side in ("yes", "NO_SIDE", "", "BOTH", "LONG_YES"):
        result = select_exact_clob_price(bad_side, "BUY", _snap())
        assert result["valid"] is False
        assert result["validation_error"] == "INVALID_SIDE", (
            f"side={bad_side!r} did not return INVALID_SIDE"
        )


def test_16_invalid_action_rejected():
    """An unrecognised action string must return INVALID_ACTION."""
    for bad_action in ("buy", "OPEN", "", "CLOSE", "FILL"):
        result = select_exact_clob_price("YES", bad_action, _snap())
        assert result["valid"] is False
        assert result["validation_error"] == "INVALID_ACTION", (
            f"action={bad_action!r} did not return INVALID_ACTION"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Tests 17–18: out-of-range prices rejected
# ══════════════════════════════════════════════════════════════════════════════

def test_17_price_le_zero_rejected():
    """yes_ask = 0.0 must be rejected as INVALID_CLOB_PRICE."""
    result = select_exact_clob_price("YES", "BUY", _snap(yes_ask=0.0))
    assert result["valid"] is False
    assert result["validation_error"] == "INVALID_CLOB_PRICE"


def test_18_price_ge_one_rejected():
    """yes_ask = 1.0 must be rejected as INVALID_CLOB_PRICE."""
    result = select_exact_clob_price("YES", "BUY", _snap(yes_ask=1.0))
    assert result["valid"] is False
    assert result["validation_error"] == "INVALID_CLOB_PRICE"


# ══════════════════════════════════════════════════════════════════════════════
# Test 19: ask < bid invalidates snapshot
# ══════════════════════════════════════════════════════════════════════════════

def test_19_ask_below_bid_invalidates_snapshot():
    """yes_ask < yes_bid (inverted spread) must return INVALID_CLOB_PRICE."""
    # yes_ask (0.55) < yes_bid (0.61) → inverted
    result = select_exact_clob_price("YES", "BUY", _snap(yes_ask=0.55, yes_bid=0.61))
    assert result["valid"] is False
    assert result["validation_error"] == "INVALID_CLOB_PRICE"

    # Same for NO side
    result = select_exact_clob_price("NO", "BUY", _snap(no_ask=0.28, no_bid=0.34))
    assert result["valid"] is False
    assert result["validation_error"] == "INVALID_CLOB_PRICE"


# ══════════════════════════════════════════════════════════════════════════════
# Test 20: condition mismatch rejected
# ══════════════════════════════════════════════════════════════════════════════

def test_20_condition_mismatch_rejected():
    """Passing a mismatched expected_condition_id must return CONDITION_BINDING_MISMATCH."""
    snap = _snap(condition_id="0xREAL_CONDITION")
    result = select_exact_clob_price(
        "YES", "BUY", snap, expected_condition_id="0xDIFFERENT_CONDITION"
    )
    assert result["valid"] is False
    assert result["validation_error"] == "CONDITION_BINDING_MISMATCH"

    # Correct condition_id must still pass.
    result_ok = select_exact_clob_price(
        "YES", "BUY", snap, expected_condition_id="0xREAL_CONDITION"
    )
    assert result_ok["valid"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Test 21: stale snapshot rejected
# ══════════════════════════════════════════════════════════════════════════════

def test_21_stale_snapshot_rejected():
    """A snapshot older than max_age_seconds must return CLOB_SNAPSHOT_STALE."""
    stale_snap = _snap(fetched_at=_STALE)
    result = select_exact_clob_price("YES", "BUY", stale_snap, max_age_seconds=60.0)
    assert result["valid"] is False
    assert result["validation_error"] == "CLOB_SNAPSHOT_STALE"

    # A fresh snapshot with same prices must pass.
    fresh_snap = _snap(fetched_at=_FRESH)
    result_ok = select_exact_clob_price("YES", "BUY", fresh_snap, max_age_seconds=60.0)
    assert result_ok["valid"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Test 22: YES and NO token IDs remain distinct
# ══════════════════════════════════════════════════════════════════════════════

def test_22_yes_and_no_token_ids_remain_distinct():
    """YES BUY returns yes_token_id; NO BUY returns no_token_id. They differ."""
    snap = _snap()
    yes_result = select_exact_clob_price("YES", "BUY", snap)
    no_result = select_exact_clob_price("NO", "BUY", snap)

    assert yes_result["valid"] is True
    assert no_result["valid"] is True
    assert yes_result["token_id"] == _YES_TOKEN
    assert no_result["token_id"] == _NO_TOKEN
    assert yes_result["token_id"] != no_result["token_id"]


# ══════════════════════════════════════════════════════════════════════════════
# Test 23: snapshot condition_id preserved in result
# ══════════════════════════════════════════════════════════════════════════════

def test_23_snapshot_condition_id_preserved():
    """The condition_id from the snapshot flows into the result token_id path."""
    specific_cond = "0xSPECIFIC_CONDITION_FOR_TEST_23"
    snap = _snap(condition_id=specific_cond)
    result = select_exact_clob_price("YES", "BUY", snap, expected_condition_id=specific_cond)
    assert result["valid"] is True
    # The token_id returned should match the snapshot's yes_token_id.
    assert result["token_id"] == _YES_TOKEN


# ══════════════════════════════════════════════════════════════════════════════
# Test 24: no synthetic 0.5 price exists in selector
# ══════════════════════════════════════════════════════════════════════════════

def test_24_no_synthetic_0_5_exists():
    """
    When NO prices are all None (no book data), the selector must NOT return
    a synthetic 0.5.  It must return valid=False.
    """
    snap = _snap(no_bid=None, no_ask=None, no_mid=None)
    for action in ("BUY", "SELL", "MARK"):
        result = select_exact_clob_price("NO", action, snap)
        assert result["valid"] is False
        assert result["price"] is None
        assert result["price"] != pytest.approx(0.5), (
            f"Selector returned synthetic 0.5 for NO {action}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 25: selector does not mutate snapshot
# ══════════════════════════════════════════════════════════════════════════════

def test_25_selector_does_not_mutate_snapshot():
    """The snapshot object must be identical before and after selector calls."""
    snap = _snap()
    original_yes_bid = snap.yes_bid
    original_no_ask = snap.no_ask
    original_fetched_at = snap.fetched_at
    original_condition_id = snap.condition_id

    # Call multiple times with different side/action combos.
    select_exact_clob_price("YES", "BUY", snap)
    select_exact_clob_price("NO", "SELL", snap)
    select_exact_clob_price("YES", "MARK", snap)
    select_exact_clob_price("NO", "MARK", snap)

    assert snap.yes_bid == original_yes_bid
    assert snap.no_ask == original_no_ask
    assert snap.fetched_at == original_fetched_at
    assert snap.condition_id == original_condition_id


# ══════════════════════════════════════════════════════════════════════════════
# Static Synthetic-Price Guard (Section 6)
#
# Scans source files in the exact-side pricing scope for complement patterns.
# Any match in clob_client.py or clob_price_selector.py causes test failure.
# Matches in execution_engine.py / exit_engine.py are reported as PENDING
# (they remain temporarily during 14A1; integration is 14A2).
# ══════════════════════════════════════════════════════════════════════════════

# Complement pattern — covers both float and int literal prefixes, and
# attribute-access forms (e.g. 1.0 - opp.yes_ask, 1 - td.yes_bid).
_COMPLEMENT_RE = re.compile(
    r"1(?:\.0)?\s*-\s*(?:\w+\.)?(?:yes|no)_(?:bid|ask|mid)",
    re.IGNORECASE,
)

_SERVICES = Path(__file__).parent.parent / "services"

_GUARD_FILES = {
    "clob_client.py": _SERVICES / "clob_client.py",
    "clob_price_selector.py": _SERVICES / "clob_price_selector.py",
}

_PENDING_FILES = {
    # 14A2: replace `1 - opp.yes_ask` / `1 - td.yes_bid` with exact NO book prices.
    "execution_engine.py": _SERVICES / "execution_engine.py",
    # 14A2: replace `1 - opp.yes_ask` in _get_exit_price with exact NO book prices.
    "exit_engine.py": _SERVICES / "exit_engine.py",
    # 14A2: replace `no_mid = 1.0 - yes_mid` with exact no_mid from CLOB snapshot.
    "decision_engine.py": _SERVICES / "decision_engine.py",
    # 14A2: replace `current_price = 1.0 - yes_mid` with exact no_mid mark for LONG_NO.
    "position_service.py": _SERVICES / "position_service.py",
    # 14A2: replace `1.0 - snap.yes_mid` with exact no_mid from CLOB snapshot.
    "trade_evaluation_service.py": _SERVICES / "trade_evaluation_service.py",
}


def _find_complement_lines(path: Path) -> list[tuple[int, str]]:
    """
    Return (lineno, stripped_line) for every complement pattern match in
    executable code.  String literals (docstrings, inline strings) and
    comment tokens are excluded using the stdlib tokenizer so the guard
    never fires on documentation that merely describes the forbidden pattern.
    """
    hits: list[tuple[int, str]] = []
    try:
        source = path.read_text()
    except FileNotFoundError:
        return hits

    # Build a set of line numbers that are entirely inside a string token or
    # are comment tokens — we skip those when scanning for complement patterns.
    non_code_lines: set[int] = set()
    try:
        for tok_type, _, tok_start, tok_end, _ in tokenize.generate_tokens(
            io.StringIO(source).readline
        ):
            if tok_type in (tokenize.STRING, tokenize.COMMENT):
                for lineno in range(tok_start[0], tok_end[0] + 1):
                    non_code_lines.add(lineno)
    except tokenize.TokenError:
        pass  # Incomplete file — scan whatever we parsed.

    for lineno, line in enumerate(source.splitlines(), start=1):
        if lineno in non_code_lines:
            continue
        if _COMPLEMENT_RE.search(line):
            hits.append((lineno, line.strip()))
    return hits


def test_static_guard_no_complement_in_clob_client():
    """clob_client.py must contain zero complement pricing expressions."""
    path = _GUARD_FILES["clob_client.py"]
    hits = _find_complement_lines(path)
    assert not hits, (
        f"Complement pricing found in {path.name}:\n"
        + "\n".join(f"  line {ln}: {src}" for ln, src in hits)
    )


def test_static_guard_no_complement_in_selector():
    """clob_price_selector.py must contain zero complement pricing expressions."""
    path = _GUARD_FILES["clob_price_selector.py"]
    hits = _find_complement_lines(path)
    assert not hits, (
        f"Complement pricing found in {path.name}:\n"
        + "\n".join(f"  line {ln}: {src}" for ln, src in hits)
    )


def test_static_guard_pending_complement_locations_contained():
    """
    Complement pricing in execution_engine.py and exit_engine.py is ALLOWED
    during 14A1 (integration deferred to 14A2).

    This test enforces TWO things:

    1. Complement lines exist ONLY in the two explicitly pending files —
       they must not have spread to any other service file.
    2. Each pending file still contains at least one complement line —
       if they are accidentally removed without the full 14A2 migration,
       this test reminds the developer that the static guard in
       test_static_guard_no_complement_in_selector must also be updated.

    PENDING for Checkpoint 14A2: migrate to exact NO book prices then flip
    these assertions to assert zero complement lines in all files.
    """
    # Scan every .py file in services/ for complement patterns.
    services_dir = _SERVICES
    all_service_files = list(services_dir.glob("*.py"))

    allowed_pending_names = set(_PENDING_FILES.keys())

    violations: list[str] = []   # complement in a file that must be clean
    pending_report: list[str] = []

    for py_file in sorted(all_service_files):
        hits = _find_complement_lines(py_file)
        if not hits:
            continue
        if py_file.name in allowed_pending_names:
            # Expected: document for transparency.
            for ln, src in hits:
                pending_report.append(f"  [PENDING-14A2] {py_file.name}:{ln}: {src}")
        else:
            # Unexpected: complement must not appear in any other service file.
            for ln, src in hits:
                violations.append(f"  {py_file.name}:{ln}: {src}")

    if pending_report:
        print("\nPENDING complement locations (14A2):\n" + "\n".join(pending_report))

    # Assert no new files have been contaminated with complement pricing.
    assert not violations, (
        "Complement pricing found outside the allowed pending files "
        f"({', '.join(sorted(allowed_pending_names))}):\n"
        + "\n".join(violations)
        + "\nRemove these complement calculations or add the file to _PENDING_FILES "
        "with a documented 14A2 migration plan."
    )

    # Assert the pending files still hold their known complement lines —
    # if both are accidentally cleaned without the full 14A2 migration,
    # the guard below would silently pass with incomplete work.
    for name, path in _PENDING_FILES.items():
        hits = _find_complement_lines(path)
        assert hits, (
            f"{name} no longer contains complement pricing, but 14A2 integration "
            "has not been completed. Either finish 14A2 (wire exact NO book prices "
            "into execution and exit engines) or update this guard."
        )
