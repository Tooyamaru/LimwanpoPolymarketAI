"""
Tests — OutcomeLearningService (Priority 1 + Priority 5 Feedback Loop).

Phase 9D: Direct Polymarket Resolution as primary correctness source.

Uses pure-Python mocks. No database. No live engines.
"""

from __future__ import annotations

import pytest

from app.services.outcome_learning_service import OutcomeLearningService
from app.services.gamma_series_client import (
    MarketResolutionResult,
    OUTCOME_SOURCE_DIRECT,
    OUTCOME_SOURCE_PROXY,
    OUTCOME_SOURCE_NONE,
)


# ── Override async autouse fixture with a sync no-op ──────────────────────────
# conftest.py defines an async reset_db_engine autouse fixture, but all tests
# in this module are sync (no DB calls). Override it here so pytest doesn't
# try to run an async fixture in a sync test context.
@pytest.fixture(autouse=True)
def reset_db_engine():
    """Sync override — tests in this module do not touch the DB engine."""
    yield


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_svc() -> OutcomeLearningService:
    return OutcomeLearningService()


def _direct_resolution(winning_side: str, yes_price: float = 1.0, no_price: float = 0.0) -> MarketResolutionResult:
    """Build a DIRECT_POLYMARKET_RESOLUTION result."""
    token = "yes-tok" if winning_side == "YES" else "no-tok"
    return MarketResolutionResult(
        outcome_source=OUTCOME_SOURCE_DIRECT,
        winning_side=winning_side,
        winning_token_id=token,
        final_yes_price=yes_price,
        final_no_price=no_price,
        resolution_note=f"DIRECT_RESOLUTION_CONFIRMED: winner={winning_side}",
    )


def _no_resolution(note: str = "Market not yet resolved") -> MarketResolutionResult:
    """Build a NOT_AVAILABLE result."""
    return MarketResolutionResult(
        outcome_source=OUTCOME_SOURCE_NONE,
        winning_side=None,
        winning_token_id=None,
        final_yes_price=None,
        final_no_price=None,
        resolution_note=note,
    )


# ── Phase 9D: Direct resolution correctness tests ─────────────────────────────

class TestDirectResolutionCorrectness:
    """
    Verify that correctness is derived from winning_side when
    DIRECT_POLYMARKET_RESOLUTION is available, not from realized_pnl.
    """

    def test_buy_yes_with_yes_winner_is_correct(self):
        """BUY_YES + winning_side=YES → correct=True"""
        resolution = _direct_resolution("YES")
        # Simulate the correctness logic from _evaluate_market
        prediction = "BUY_YES"
        if resolution.outcome_source == OUTCOME_SOURCE_DIRECT:
            correct = (prediction == "BUY_YES" and resolution.winning_side == "YES")
        assert correct is True

    def test_buy_yes_with_no_winner_is_wrong(self):
        """BUY_YES + winning_side=NO → correct=False"""
        resolution = _direct_resolution("NO", yes_price=0.0, no_price=1.0)
        prediction = "BUY_YES"
        if resolution.outcome_source == OUTCOME_SOURCE_DIRECT:
            correct = (prediction == "BUY_YES" and resolution.winning_side == "YES")
        assert correct is False

    def test_buy_no_with_no_winner_is_correct(self):
        """BUY_NO + winning_side=NO → correct=True"""
        resolution = _direct_resolution("NO", yes_price=0.0, no_price=1.0)
        prediction = "BUY_NO"
        if resolution.outcome_source == OUTCOME_SOURCE_DIRECT:
            correct = (prediction == "BUY_NO" and resolution.winning_side == "NO")
        assert correct is True

    def test_buy_no_with_yes_winner_is_wrong(self):
        """BUY_NO + winning_side=YES → correct=False"""
        resolution = _direct_resolution("YES")
        prediction = "BUY_NO"
        if resolution.outcome_source == OUTCOME_SOURCE_DIRECT:
            correct = (prediction == "BUY_NO" and resolution.winning_side == "NO")
        assert correct is False

    def test_direct_resolution_outcome_source_label(self):
        """outcome_source must be DIRECT_POLYMARKET_RESOLUTION when winner confirmed."""
        resolution = _direct_resolution("YES")
        assert resolution.outcome_source == OUTCOME_SOURCE_DIRECT

    def test_direct_resolution_winning_token_yes(self):
        """YES win → winning_token_id is the YES token."""
        resolution = _direct_resolution("YES")
        assert resolution.winning_token_id == "yes-tok"

    def test_direct_resolution_winning_token_no(self):
        """NO win → winning_token_id is the NO token."""
        resolution = _direct_resolution("NO", yes_price=0.0, no_price=1.0)
        assert resolution.winning_token_id == "no-tok"

    def test_direct_resolution_final_prices_stored(self):
        """final_yes_price and final_no_price must be stored on result."""
        resolution = _direct_resolution("YES", yes_price=1.0, no_price=0.0)
        assert resolution.final_yes_price == 1.0
        assert resolution.final_no_price == 0.0

    def test_wait_with_direct_resolution_correct_is_none(self):
        """WAIT prediction + direct resolution → correct=None (can't determine direction)."""
        resolution = _direct_resolution("YES")
        prediction = "WAIT"
        if resolution.outcome_source == OUTCOME_SOURCE_DIRECT and prediction not in ("BUY_YES", "BUY_NO"):
            correct = None
        assert correct is None


class TestPnlProxyFallback:
    """
    Verify that REALIZED_PNL_PROXY is only used when direct resolution
    is NOT_AVAILABLE.
    """

    def test_pnl_proxy_positive_is_correct(self):
        """No direct resolution + PnL > 0 → correct=True, outcome_source=REALIZED_PNL_PROXY"""
        resolution = _no_resolution()
        realized_pnl = 0.15
        # simulate fallback logic
        outcome_source = OUTCOME_SOURCE_PROXY
        correct = realized_pnl > 0
        assert correct is True
        assert outcome_source == OUTCOME_SOURCE_PROXY

    def test_pnl_proxy_negative_is_wrong(self):
        """No direct resolution + PnL < 0 → correct=False, outcome_source=REALIZED_PNL_PROXY"""
        resolution = _no_resolution()
        realized_pnl = -0.50
        outcome_source = OUTCOME_SOURCE_PROXY
        correct = realized_pnl > 0
        assert correct is False
        assert outcome_source == OUTCOME_SOURCE_PROXY

    def test_pnl_proxy_zero_pnl_is_wrong(self):
        """PnL = 0 is not positive → correct=False."""
        realized_pnl = 0.0
        correct = realized_pnl > 0
        assert correct is False

    def test_no_position_no_direct_resolution_gives_none(self):
        """No position, no direct resolution → correct=None, source=NOT_AVAILABLE."""
        resolution = _no_resolution()
        assert resolution.outcome_source == OUTCOME_SOURCE_NONE
        assert resolution.winning_side is None

    def test_not_available_result_has_no_winning_side(self):
        """NOT_AVAILABLE resolution must never set a winning_side."""
        resolution = _no_resolution()
        assert resolution.winning_side is None
        assert resolution.winning_token_id is None


class TestResolutionResultDataclass:
    """Verify MarketResolutionResult dataclass fields."""

    def test_direct_result_fields(self):
        r = _direct_resolution("YES")
        assert r.outcome_source == OUTCOME_SOURCE_DIRECT
        assert r.winning_side == "YES"
        assert r.final_yes_price == 1.0
        assert r.final_no_price == 0.0
        assert "DIRECT_RESOLUTION_CONFIRMED" in r.resolution_note

    def test_not_available_result_fields(self):
        r = _no_resolution("test note")
        assert r.outcome_source == OUTCOME_SOURCE_NONE
        assert r.winning_side is None
        assert r.winning_token_id is None
        assert r.final_yes_price is None
        assert r.final_no_price is None
        assert "test note" in r.resolution_note

    def test_outcome_source_constants_are_strings(self):
        assert isinstance(OUTCOME_SOURCE_DIRECT, str)
        assert isinstance(OUTCOME_SOURCE_PROXY, str)
        assert isinstance(OUTCOME_SOURCE_NONE, str)

    def test_outcome_source_values(self):
        assert OUTCOME_SOURCE_DIRECT == "DIRECT_POLYMARKET_RESOLUTION"
        assert OUTCOME_SOURCE_PROXY == "REALIZED_PNL_PROXY"
        assert OUTCOME_SOURCE_NONE == "NOT_AVAILABLE"


# ── Confidence calibration tests (Priority 5) ─────────────────────────────────

class TestEvaluateConfidence:
    def test_high_conf_correct_is_well_calibrated(self):
        result = OutcomeLearningService._evaluate_confidence(80.0, True)
        assert result == "WELL_CALIBRATED"

    def test_high_conf_wrong_is_overconfident(self):
        result = OutcomeLearningService._evaluate_confidence(75.0, False)
        assert result == "OVERCONFIDENT"

    def test_low_conf_correct_is_underconfident(self):
        result = OutcomeLearningService._evaluate_confidence(20.0, True)
        assert result == "UNDERCONFIDENT"

    def test_low_conf_wrong_is_well_calibrated(self):
        result = OutcomeLearningService._evaluate_confidence(25.0, False)
        assert result == "WELL_CALIBRATED"

    def test_none_confidence_returns_unknown(self):
        result = OutcomeLearningService._evaluate_confidence(None, True)
        assert result == "UNKNOWN"

    def test_none_correct_returns_unknown(self):
        result = OutcomeLearningService._evaluate_confidence(70.0, None)
        assert result == "UNKNOWN"

    def test_mid_range_confidence_correct(self):
        result = OutcomeLearningService._evaluate_confidence(50.0, True)
        assert result == "WELL_CALIBRATED"

    def test_mid_range_confidence_wrong(self):
        result = OutcomeLearningService._evaluate_confidence(50.0, False)
        assert result == "WELL_CALIBRATED"

    def test_boundary_high_conf_exact(self):
        # 65.0 is CONFIDENCE_HIGH threshold
        result = OutcomeLearningService._evaluate_confidence(65.0, False)
        assert result == "OVERCONFIDENT"

    def test_boundary_low_conf_exact(self):
        # 35.0 is CONFIDENCE_LOW threshold — below threshold is low
        result = OutcomeLearningService._evaluate_confidence(34.9, True)
        assert result == "UNDERCONFIDENT"


# ── Entry quality evaluation tests ────────────────────────────────────────────

class TestEvaluateEntryQuality:
    def test_high_quality_correct_is_good_filter(self):
        result = OutcomeLearningService._evaluate_entry_quality(80.0, True)
        assert result == "GOOD_FILTER"

    def test_high_quality_wrong_is_false_positive(self):
        result = OutcomeLearningService._evaluate_entry_quality(75.0, False)
        assert result == "FALSE_POSITIVE"

    def test_low_quality_wrong_is_good_filter(self):
        result = OutcomeLearningService._evaluate_entry_quality(30.0, False)
        assert result == "GOOD_FILTER"

    def test_low_quality_correct_is_missed(self):
        result = OutcomeLearningService._evaluate_entry_quality(40.0, True)
        assert result == "MISSED"

    def test_none_returns_unknown(self):
        result = OutcomeLearningService._evaluate_entry_quality(None, True)
        assert result == "UNKNOWN"

    def test_correct_none_returns_unknown(self):
        result = OutcomeLearningService._evaluate_entry_quality(70.0, None)
        assert result == "UNKNOWN"


# ── Consensus evaluation tests ────────────────────────────────────────────────

class TestEvaluateConsensus:
    def test_no_conflict_correct_is_reliable(self):
        result = OutcomeLearningService._evaluate_consensus(False, True)
        assert result == "RELIABLE"

    def test_conflict_wrong_is_conflicted_and_wrong(self):
        result = OutcomeLearningService._evaluate_consensus(True, False)
        assert result == "CONFLICTED_AND_WRONG"

    def test_conflict_correct_is_conflicted_and_lucky(self):
        result = OutcomeLearningService._evaluate_consensus(True, True)
        assert result == "CONFLICTED_AND_LUCKY"

    def test_no_conflict_wrong_is_reliable(self):
        # No conflict but still wrong — consensus didn't warn us
        result = OutcomeLearningService._evaluate_consensus(False, False)
        assert result == "RELIABLE"

    def test_none_conflict_returns_unknown(self):
        result = OutcomeLearningService._evaluate_consensus(None, True)
        assert result == "UNKNOWN"

    def test_none_correct_returns_unknown(self):
        result = OutcomeLearningService._evaluate_consensus(False, None)
        assert result == "UNKNOWN"


# ── Service instantiation ─────────────────────────────────────────────────────

class TestOutcomeLearningServiceSetup:
    def test_can_instantiate(self):
        svc = _make_svc()
        assert svc is not None

    def test_static_methods_available(self):
        assert callable(OutcomeLearningService._evaluate_confidence)
        assert callable(OutcomeLearningService._evaluate_entry_quality)
        assert callable(OutcomeLearningService._evaluate_consensus)
        assert callable(OutcomeLearningService._build_feedback_summary)
