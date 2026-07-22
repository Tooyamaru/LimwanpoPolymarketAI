"""
14A2A — Exact-side CLOB persistence field tests.

Verifies that:
  - Opportunity, TradeDecision, and Order models accept exact YES/NO side fields
  - Values are stored unchanged (non-complementary)
  - Historical callers omitting new fields continue to work
  - Migration SQL is additive-only (no DROP / DELETE / TRUNCATE / complement backfill)
  - No executable complement derivation exists in modified production files

Non-complementary test values:
    yes_bid = 0.61, yes_ask = 0.64
    no_bid  = 0.31, no_ask  = 0.34
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────

YES_BID = 0.61
YES_ASK = 0.64
NO_BID  = 0.31
NO_ASK  = 0.34
YES_MID = 0.625
NO_MID  = 0.325

NOW_UTC = datetime.now(timezone.utc)

# Files modified in 14A2A — used for static complement guard (test 25-27)
_REPO_ROOT = Path(__file__).parents[3]
_MODIFIED_FILES = [
    _REPO_ROOT / "backend/app/models/opportunity.py",
    _REPO_ROOT / "backend/app/models/trade_decision.py",
    _REPO_ROOT / "backend/app/models/order.py",
    _REPO_ROOT / "backend/app/repositories/opportunity_repository.py",
    _REPO_ROOT / "backend/app/repositories/trade_decision_repository.py",
    _REPO_ROOT / "backend/app/repositories/order_repository.py",
    _REPO_ROOT / "backend/app/core/database.py",
]

# Patterns that must NOT appear as executable code in the modified files.
# Comments and string literals that merely describe the pattern are acceptable.
_COMPLEMENT_PATTERNS = [
    r"1\s*-\s*yes_bid",
    r"1\s*-\s*yes_ask",
    r"1\s*-\s*yes_mid",
    r"1\.0\s*-\s*yes_bid",
    r"1\.0\s*-\s*yes_ask",
    r"1\.0\s*-\s*yes_mid",
]


def _executable_lines(path: Path) -> list[str]:
    """
    Return only genuinely executable source lines from a Python file.

    Excludes:
      - blank lines
      - comment lines (# ...)
      - lines that are entirely within a string literal (docstrings, multi-line
        strings) — detected via Python's tokenize module so no regex heuristics.
    """
    import io
    import tokenize as _tok

    source = path.read_text(encoding="utf-8")

    # Collect every line number that is covered by a STRING token
    string_line_nos: set[int] = set()
    try:
        tokens = _tok.generate_tokens(io.StringIO(source).readline)
        for tok_type, _, tok_start, tok_end, _ in tokens:
            if tok_type == _tok.STRING:
                for lineno in range(tok_start[0], tok_end[0] + 1):
                    string_line_nos.add(lineno)
    except _tok.TokenError:
        pass  # partial source — fall back to empty exclusion set

    result = []
    for lineno, raw in enumerate(source.splitlines(), start=1):
        if lineno in string_line_nos:
            continue
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            result.append(stripped)
    return result


# ── Opportunity tests (1-6) ───────────────────────────────────────────────────

def test_opportunity_accepts_exact_no_bid():
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        no_bid=NO_BID,
    )
    assert opp.no_bid == NO_BID


def test_opportunity_accepts_exact_no_ask():
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        no_ask=NO_ASK,
    )
    assert opp.no_ask == NO_ASK


def test_opportunity_accepts_exact_no_mid():
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        no_mid=NO_MID,
    )
    assert opp.no_mid == NO_MID


def test_opportunity_accepts_spread_no():
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        spread_no=round(NO_ASK - NO_BID, 4),
    )
    assert opp.spread_no == pytest.approx(NO_ASK - NO_BID, abs=1e-9)


def test_opportunity_accepts_timezone_aware_clob_fetched_at():
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        clob_fetched_at=NOW_UTC,
    )
    assert opp.clob_fetched_at is not None
    assert opp.clob_fetched_at.tzinfo is not None


def test_opportunity_exact_no_values_are_non_complementary():
    """no_bid and no_ask must not equal 1 - yes_ask and 1 - yes_bid respectively."""
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xABC",
        asset="BTC",
        timeframe="5m",
        opportunity_score=55.0,
        score_mid_movement=20.0,
        score_spread=10.0,
        score_depth_imbalance=10.0,
        score_signal_activity=10.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        yes_bid=YES_BID,
        yes_ask=YES_ASK,
        no_bid=NO_BID,
        no_ask=NO_ASK,
    )
    # These values are intentionally non-complementary
    assert opp.no_bid != pytest.approx(1 - opp.yes_ask, abs=1e-9)
    assert opp.no_ask != pytest.approx(1 - opp.yes_bid, abs=1e-9)


# ── TradeDecision tests (7-12) ────────────────────────────────────────────────

def _make_td(**kwargs):
    from app.models.trade_decision import TradeDecision
    base = dict(
        condition_id="0xDEF",
        asset="ETH",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        status="PENDING",
        opportunity_score=60.0,
        direction="BUY_YES",
        decided_at=NOW_UTC,
    )
    base.update(kwargs)
    return TradeDecision(**base)


def test_trade_decision_accepts_all_exact_yes_fields():
    td = _make_td(yes_bid=YES_BID, yes_ask=YES_ASK, yes_mid=YES_MID, spread_yes=round(YES_ASK - YES_BID, 4))
    assert td.yes_bid == YES_BID
    assert td.yes_ask == YES_ASK
    assert td.yes_mid == YES_MID
    assert td.spread_yes == pytest.approx(YES_ASK - YES_BID, abs=1e-9)


def test_trade_decision_accepts_all_exact_no_fields():
    td = _make_td(no_bid=NO_BID, no_ask=NO_ASK, no_mid=NO_MID, spread_no=round(NO_ASK - NO_BID, 4))
    assert td.no_bid == NO_BID
    assert td.no_ask == NO_ASK
    assert td.no_mid == NO_MID
    assert td.spread_no == pytest.approx(NO_ASK - NO_BID, abs=1e-9)


def test_trade_decision_stores_selected_yes_token():
    yes_token = "0xYES_TOKEN_ID_ABCDEF"
    td = _make_td(selected_token_id=yes_token, selected_price_source="yes_ask")
    assert td.selected_token_id == yes_token


def test_trade_decision_stores_selected_no_token():
    no_token = "0xNO_TOKEN_ID_FEDCBA"
    td = _make_td(selected_token_id=no_token, selected_price_source="no_ask")
    assert td.selected_token_id == no_token


def test_trade_decision_stores_selected_price_source_yes_ask():
    td = _make_td(selected_price_source="yes_ask")
    assert td.selected_price_source == "yes_ask"


def test_trade_decision_stores_selected_price_source_no_ask():
    td = _make_td(selected_price_source="no_ask")
    assert td.selected_price_source == "no_ask"


# ── Order tests (13-16) ───────────────────────────────────────────────────────

def _make_order(**kwargs):
    from app.models.order import Order
    base = dict(
        decision_id=1,
        condition_id="0xGHI",
        asset="SOL",
        timeframe="5m",
        side="LONG_YES",
        order_type="MARKET",
        quantity=10.0,
        requested_price=YES_ASK,
        filled_price=YES_ASK,
        status="FILLED",
        created_at=NOW_UTC,
        filled_at=NOW_UTC,
    )
    base.update(kwargs)
    return Order(**base)


def test_order_stores_exact_yes_token_id():
    yes_token = "0xYES_TOKEN_111"
    order = _make_order(token_id=yes_token, side="LONG_YES")
    assert order.token_id == yes_token


def test_order_stores_exact_no_token_id():
    no_token = "0xNO_TOKEN_222"
    order = _make_order(token_id=no_token, side="LONG_NO", requested_price=NO_ASK, filled_price=NO_ASK)
    assert order.token_id == no_token


def test_order_stores_exact_price_source():
    order = _make_order(price_source="yes_ask")
    assert order.price_source == "yes_ask"


def test_order_stores_timezone_aware_clob_fetched_at():
    order = _make_order(clob_fetched_at=NOW_UTC)
    assert order.clob_fetched_at is not None
    assert order.clob_fetched_at.tzinfo is not None


# ── Backward compatibility tests (17-19) ─────────────────────────────────────

def test_historical_opportunity_caller_may_omit_new_fields():
    """Historical callers without no_bid/no_ask/clob_fetched_at must still work."""
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xHIST1",
        asset="XRP",
        timeframe="1H",
        opportunity_score=30.0,
        score_mid_movement=10.0,
        score_spread=5.0,
        score_depth_imbalance=5.0,
        score_signal_activity=5.0,
        score_discovery=5.0,
        direction="NEUTRAL",
        evaluated_at=NOW_UTC,
        yes_bid=0.49,
        yes_ask=0.51,
    )
    assert opp.no_bid is None
    assert opp.no_ask is None
    assert opp.clob_fetched_at is None


def test_historical_trade_decision_caller_may_omit_new_fields():
    """Historical callers without NO-side / selected_token fields must still work."""
    td = _make_td(yes_bid=YES_BID, yes_ask=YES_ASK)
    assert td.no_bid is None
    assert td.no_ask is None
    assert td.no_mid is None
    assert td.spread_no is None
    assert td.clob_fetched_at is None
    assert td.selected_token_id is None
    assert td.selected_price_source is None


def test_historical_order_caller_may_omit_new_fields():
    """Historical callers without token_id/price_source/clob_fetched_at must still work."""
    order = _make_order()
    assert order.token_id is None
    assert order.price_source is None
    assert order.clob_fetched_at is None


# ── Migration SQL tests (20-24) ───────────────────────────────────────────────

def _get_migration_stmts() -> list[str]:
    """Extract all migration SQL statements from database.py init_db()."""
    src = (_REPO_ROOT / "backend/app/core/database.py").read_text(encoding="utf-8")
    # Extract string literals inside the all_migrations list
    return re.findall(r'"(ALTER TABLE[^"]+|CREATE INDEX[^"]+|UPDATE[^"]+)"', src)


def test_migration_contains_add_column_if_not_exists():
    stmts = _get_migration_stmts()
    add_col_stmts = [s for s in stmts if "ADD COLUMN IF NOT EXISTS" in s]
    # 14A2A adds at least the 10 new columns
    assert len(add_col_stmts) >= 10, f"Expected ≥10 ADD COLUMN IF NOT EXISTS, got {len(add_col_stmts)}"


def test_migration_contains_no_drop_table():
    src = (_REPO_ROOT / "backend/app/core/database.py").read_text(encoding="utf-8")
    assert "DROP TABLE" not in src.upper()


def test_migration_contains_no_delete_from():
    stmts = _get_migration_stmts()
    delete_stmts = [s for s in stmts if s.strip().upper().startswith("DELETE FROM")]
    assert delete_stmts == [], f"Unexpected DELETE FROM in migrations: {delete_stmts}"


def test_migration_contains_no_truncate():
    stmts = _get_migration_stmts()
    truncate_stmts = [s for s in stmts if "TRUNCATE" in s.upper()]
    assert truncate_stmts == [], f"Unexpected TRUNCATE in migrations: {truncate_stmts}"


def test_migration_does_not_contain_complement_backfill():
    """Migration SQL must not derive NO values from YES via complement arithmetic."""
    stmts = _get_migration_stmts()
    for stmt in stmts:
        for pat in _COMPLEMENT_PATTERNS:
            assert not re.search(pat, stmt, re.IGNORECASE), (
                f"Complement backfill pattern '{pat}' found in migration: {stmt}"
            )


# ── Value integrity tests (25-27) ─────────────────────────────────────────────

def test_exact_values_survive_repository_assignment_unchanged():
    """Values assigned to model fields must come back exactly as-is."""
    from app.models.opportunity import Opportunity
    opp = Opportunity(
        condition_id="0xINT",
        asset="BTC",
        timeframe="5m",
        opportunity_score=75.0,
        score_mid_movement=25.0,
        score_spread=15.0,
        score_depth_imbalance=15.0,
        score_signal_activity=15.0,
        score_discovery=5.0,
        direction="BUY_YES",
        evaluated_at=NOW_UTC,
        yes_bid=YES_BID,
        yes_ask=YES_ASK,
        yes_mid=YES_MID,
        no_bid=NO_BID,
        no_ask=NO_ASK,
        no_mid=NO_MID,
        clob_fetched_at=NOW_UTC,
    )
    assert opp.yes_bid == YES_BID
    assert opp.yes_ask == YES_ASK
    assert opp.yes_mid == YES_MID
    assert opp.no_bid == NO_BID
    assert opp.no_ask == NO_ASK
    assert opp.no_mid == NO_MID


def test_yes_and_no_token_ids_remain_distinct():
    """YES and NO token IDs stored on an order must be distinct values."""
    yes_token = "0xYES_DISTINCT_TOKEN"
    no_token  = "0xNO_DISTINCT_TOKEN"
    assert yes_token != no_token  # baseline sanity

    order_yes = _make_order(token_id=yes_token, side="LONG_YES")
    order_no  = _make_order(token_id=no_token,  side="LONG_NO", requested_price=NO_ASK, filled_price=NO_ASK)
    assert order_yes.token_id != order_no.token_id


def test_no_synthetic_0_5_default_exists():
    """
    No modified production file may contain a hardcoded 0.5 default for
    NO-side price fields.  The ORM default for all new fields is NULL.
    """
    for path in _MODIFIED_FILES:
        lines = _executable_lines(path)
        for line in lines:
            # Allow numeric literals in general; only flag default=0.5 for NO fields
            if re.search(r'no_bid.*default\s*=\s*0\.5', line, re.IGNORECASE):
                pytest.fail(f"Synthetic 0.5 default for no_bid in {path}: {line!r}")
            if re.search(r'no_ask.*default\s*=\s*0\.5', line, re.IGNORECASE):
                pytest.fail(f"Synthetic 0.5 default for no_ask in {path}: {line!r}")
            if re.search(r'no_mid.*default\s*=\s*0\.5', line, re.IGNORECASE):
                pytest.fail(f"Synthetic 0.5 default for no_mid in {path}: {line!r}")


# ── Static complement guard (section 9) ───────────────────────────────────────

@pytest.mark.parametrize("path", _MODIFIED_FILES)
@pytest.mark.parametrize("pattern", _COMPLEMENT_PATTERNS)
def test_no_executable_complement_derivation(path: Path, pattern: str):
    """
    Executable source lines in modified files must not contain complement
    arithmetic patterns such as `1 - yes_bid`, `1.0 - yes_ask`, etc.
    Comments describing the forbidden pattern are acceptable.
    """
    lines = _executable_lines(path)
    for line in lines:
        assert not re.search(pattern, line, re.IGNORECASE), (
            f"Complement derivation '{pattern}' found in {path.name}:\n  {line!r}"
        )
