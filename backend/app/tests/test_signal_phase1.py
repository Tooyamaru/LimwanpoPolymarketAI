"""
Phase 1 AI Signal Engine — unit and regression tests.

Unit tests
----------
  test_compute_confidence_*    — verify confidence scoring formula
  test_detect_regime_*         — verify regime classification

Regression tests (strategy engine integration)
---------------
  test_make_decision_*         — verify _make_decision with confidence gate
"""

import pytest

from app.services.signal_confidence import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    REGIME_RANGING,
    REGIME_TRENDING_DOWN,
    REGIME_TRENDING_UP,
    REGIME_UNKNOWN,
    REGIME_VOLATILE,
    compute_confidence,
    detect_regime,
)
from app.services.strategy_engine import _make_decision


# ══════════════════════════════════════════════════════════════════════════════
# Confidence Score Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeConfidence:

    def test_seed_deviation_high_severity_gives_high_confidence(self):
        score = compute_confidence(
            signal_type="SEED_DEVIATION",
            severity="HIGH",
            seed_deviation=0.08,
            spread_after=0.01,
        )
        assert score >= CONFIDENCE_HIGH, f"Expected >= {CONFIDENCE_HIGH}, got {score}"

    def test_seed_deviation_low_severity_gives_low_confidence(self):
        score = compute_confidence(
            signal_type="SEED_DEVIATION",
            severity="LOW",
            seed_deviation=0.012,
            spread_after=0.04,
        )
        assert score < CONFIDENCE_HIGH, f"Expected < {CONFIDENCE_HIGH}, got {score}"

    def test_mid_move_medium_severity(self):
        score = compute_confidence(
            signal_type="MID_MOVE",
            severity="MEDIUM",
            yes_mid_delta=0.015,
            spread_after=0.02,
        )
        assert 0 < score < 100, f"Score out of range: {score}"
        assert score < CONFIDENCE_HIGH, "MID_MOVE MEDIUM should not reach HIGH tier"

    def test_spread_change_low_severity_gives_lowest_score(self):
        score = compute_confidence(
            signal_type="SPREAD_CHANGE",
            severity="LOW",
            spread_after=0.04,
        )
        spread_high = compute_confidence(
            signal_type="SEED_DEVIATION",
            severity="HIGH",
            seed_deviation=0.10,
            spread_after=0.01,
        )
        assert score < spread_high, "SPREAD_CHANGE LOW should score below SEED_DEVIATION HIGH"

    def test_tight_spread_bonus_increases_score(self):
        tight = compute_confidence(
            signal_type="MID_MOVE",
            severity="HIGH",
            yes_mid_delta=0.03,
            spread_after=0.005,
        )
        wide = compute_confidence(
            signal_type="MID_MOVE",
            severity="HIGH",
            yes_mid_delta=0.03,
            spread_after=0.05,
        )
        assert tight > wide, "Tighter spread should produce higher confidence"

    def test_score_clamped_to_100(self):
        score = compute_confidence(
            signal_type="SEED_DEVIATION",
            severity="HIGH",
            seed_deviation=0.99,    # extreme
            spread_after=0.001,
        )
        assert score <= 100.0, f"Score must be clamped to 100, got {score}"

    def test_score_never_negative(self):
        score = compute_confidence(
            signal_type="SPREAD_CHANGE",
            severity="LOW",
            spread_after=0.10,
        )
        assert score >= 0.0, f"Score must never be negative, got {score}"

    def test_unknown_signal_type_falls_back(self):
        score = compute_confidence(
            signal_type="UNKNOWN_TYPE",
            severity="LOW",
        )
        assert score >= 0.0

    def test_missing_optional_params_ok(self):
        score = compute_confidence(
            signal_type="MID_MOVE",
            severity="MEDIUM",
        )
        assert score >= 0.0

    def test_confidence_ranked_correctly_by_type(self):
        """SEED_DEVIATION should outrank MID_MOVE, which outranks SPREAD_CHANGE."""
        sd = compute_confidence("SEED_DEVIATION", "HIGH", seed_deviation=0.05)
        mm = compute_confidence("MID_MOVE", "HIGH", yes_mid_delta=0.05)
        sc = compute_confidence("SPREAD_CHANGE", "HIGH", yes_mid_delta=0.05)
        assert sd > mm >= sc, f"Ranking wrong: SD={sd} MM={mm} SC={sc}"


# ══════════════════════════════════════════════════════════════════════════════
# Market Regime Detection Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectRegime:

    def test_insufficient_data_returns_unknown(self):
        assert detect_regime([]) == REGIME_UNKNOWN
        assert detect_regime([0.50]) == REGIME_UNKNOWN
        assert detect_regime([0.50, 0.50]) == REGIME_UNKNOWN

    def test_tight_seed_clustering_is_ranging(self):
        mids = [0.500, 0.501, 0.499, 0.500, 0.501, 0.499]
        assert detect_regime(mids) == REGIME_RANGING

    def test_upward_drift_is_trending_up(self):
        mids = [0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56]
        result = detect_regime(mids)
        assert result == REGIME_TRENDING_UP, f"Expected TRENDING_UP, got {result}"

    def test_downward_drift_is_trending_down(self):
        mids = [0.56, 0.55, 0.54, 0.53, 0.52, 0.51, 0.50]
        result = detect_regime(mids)
        assert result == REGIME_TRENDING_DOWN, f"Expected TRENDING_DOWN, got {result}"

    def test_high_variance_no_trend_is_volatile(self):
        mids = [0.50, 0.54, 0.48, 0.55, 0.47, 0.53, 0.49]
        result = detect_regime(mids)
        assert result in (REGIME_VOLATILE, REGIME_RANGING), f"Unexpected: {result}"

    def test_exactly_at_seed_is_ranging(self):
        mids = [0.50] * 8
        assert detect_regime(mids) == REGIME_RANGING

    def test_small_seed_deviation_without_trend_is_ranging(self):
        mids = [0.502, 0.503, 0.501, 0.502, 0.503, 0.502]
        result = detect_regime(mids)
        assert result == REGIME_RANGING, f"Expected RANGING for small deviation, got {result}"

    def test_three_point_minimum(self):
        mids = [0.50, 0.55, 0.60]
        result = detect_regime(mids)
        assert result in (REGIME_RANGING, REGIME_TRENDING_UP, REGIME_TRENDING_DOWN, REGIME_VOLATILE)


# ══════════════════════════════════════════════════════════════════════════════
# Strategy Engine _make_decision Regression Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMakeDecision:

    # ── Pre-existing rules (regression) ──────────────────────────────────────

    def test_high_spread_always_skips(self):
        decision, reason = _make_decision(
            score=90.0, direction="BUY_YES", spread_yes=0.05
        )
        assert decision == "SKIP"
        assert reason == "HIGH_SPREAD"

    def test_neutral_direction_skips(self):
        decision, reason = _make_decision(
            score=80.0, direction="NEUTRAL", spread_yes=0.01
        )
        assert decision == "SKIP"
        assert reason == "NEUTRAL_DIRECTION"

    def test_high_score_buy_yes_opens_long_yes(self):
        decision, reason = _make_decision(
            score=60.0, direction="BUY_YES", spread_yes=0.01,
            signal_confidence=80.0,
        )
        assert decision == "OPEN_LONG_YES"
        assert reason is None

    def test_high_score_buy_no_opens_long_no(self):
        decision, reason = _make_decision(
            score=60.0, direction="BUY_NO", spread_yes=0.01,
            signal_confidence=80.0,
        )
        assert decision == "OPEN_LONG_NO"
        assert reason is None

    def test_medium_score_watch(self):
        decision, _ = _make_decision(
            score=30.0, direction="BUY_YES", spread_yes=0.01
        )
        assert decision == "WATCH"

    def test_low_score_skip(self):
        decision, reason = _make_decision(
            score=10.0, direction="BUY_YES", spread_yes=0.01
        )
        assert decision == "SKIP"
        assert reason == "LOW_SCORE"

    # ── Phase 1: Signal confidence gate ──────────────────────────────────────

    def test_low_confidence_blocks_open_long(self):
        """A signal below MIN_SIGNAL_CONFIDENCE should block an open-long decision."""
        decision, reason = _make_decision(
            score=60.0,
            direction="BUY_YES",
            spread_yes=0.01,
            signal_confidence=10.0,   # below 25.0 threshold
            mtf_confirmed=False,
        )
        assert decision == "SKIP"
        assert reason == "LOW_SIGNAL_CONFIDENCE"

    def test_sufficient_confidence_allows_open_long(self):
        decision, reason = _make_decision(
            score=60.0,
            direction="BUY_YES",
            spread_yes=0.01,
            signal_confidence=30.0,   # above 25.0 threshold
            mtf_confirmed=False,
        )
        assert decision == "OPEN_LONG_YES"
        assert reason is None

    def test_mtf_confirmed_lowers_confidence_threshold(self):
        """MTF-confirmed signal should pass at a lower confidence threshold."""
        decision, reason = _make_decision(
            score=60.0,
            direction="BUY_YES",
            spread_yes=0.01,
            signal_confidence=18.0,   # below 25.0 but above MTF threshold (15.0)
            mtf_confirmed=True,
        )
        assert decision == "OPEN_LONG_YES"
        assert reason is None

    def test_no_signal_confidence_does_not_block(self):
        """If no signal exists for the market, the gate is bypassed."""
        decision, _ = _make_decision(
            score=60.0,
            direction="BUY_YES",
            spread_yes=0.01,
            signal_confidence=None,
        )
        assert decision == "OPEN_LONG_YES"

    def test_confidence_gate_only_for_open_long(self):
        """Confidence gate must not block WATCH decisions."""
        decision, _ = _make_decision(
            score=30.0,
            direction="BUY_YES",
            spread_yes=0.01,
            signal_confidence=5.0,    # very low, but score < SCORE_OPEN
        )
        assert decision == "WATCH"

    def test_spread_gate_beats_confidence_gate(self):
        """HIGH_SPREAD check must fire before confidence gate."""
        decision, reason = _make_decision(
            score=80.0,
            direction="BUY_YES",
            spread_yes=0.05,
            signal_confidence=100.0,  # perfect confidence
        )
        assert decision == "SKIP"
        assert reason == "HIGH_SPREAD"
