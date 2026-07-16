"""
Tests — PortfolioAllocationService (Priority 4).

Tests pure-Python allocation logic with mock objects.
No database, no async.
"""

from __future__ import annotations

import pytest

from app.services.portfolio_allocation_service import (
    MAX_CONCURRENT_POSITIONS,
    MIN_ALLOCATION_SCORE,
    NON_TRADABLE_QUALITIES,
    W_CONFIDENCE,
    W_MARKET_QUALITY,
    W_OPPORTUNITY,
    W_SPREAD,
    AllocationDecision,
    PortfolioAllocationService,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_svc() -> PortfolioAllocationService:
    return PortfolioAllocationService()


def _decision(
    action: str = "ENTER",
    asset: str = "BTC",
    condition_id: str = "c1",
    timeframe: str = "5m",
    allocation_score: float | None = 75.0,
    rank: int | None = 1,
    reason: str = "test",
    market_quality: str | None = "Excellent",
) -> AllocationDecision:
    return AllocationDecision(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        action=action,
        reason=reason,
        allocation_score=allocation_score,
        rank=rank,
        market_quality=market_quality,
    )


# ── Constants tests ───────────────────────────────────────────────────────────

class TestConstants:
    def test_non_tradable_qualities_complete(self):
        assert "BAD" in NON_TRADABLE_QUALITIES
        assert "High Risk" in NON_TRADABLE_QUALITIES
        assert "Illiquid" in NON_TRADABLE_QUALITIES
        assert "Avoid" in NON_TRADABLE_QUALITIES

    def test_tradable_qualities_not_in_set(self):
        assert "Excellent" not in NON_TRADABLE_QUALITIES
        assert "Healthy" not in NON_TRADABLE_QUALITIES
        assert "GOOD" not in NON_TRADABLE_QUALITIES
        assert "AVERAGE" not in NON_TRADABLE_QUALITIES

    def test_weights_sum_to_one(self):
        total = W_OPPORTUNITY + W_MARKET_QUALITY + W_CONFIDENCE + W_SPREAD
        assert abs(total - 1.0) < 0.001

    def test_min_score_positive(self):
        assert MIN_ALLOCATION_SCORE > 0.0

    def test_max_concurrent_positive(self):
        assert MAX_CONCURRENT_POSITIONS > 0


# ── AllocationDecision dataclass tests ───────────────────────────────────────

class TestAllocationDecision:
    def test_defaults_are_none(self):
        d = AllocationDecision(
            condition_id="c1", asset="BTC", timeframe="5m",
            action="ENTER", reason="test", allocation_score=80.0, rank=1,
        )
        assert d.opportunity_score is None
        assert d.confidence is None
        assert d.spread_tightness is None

    def test_enter_action(self):
        d = _decision(action="ENTER")
        assert d.action == "ENTER"

    def test_defer_action(self):
        d = _decision(action="DEFER", rank=None)
        assert d.action == "DEFER"
        assert d.rank is None

    def test_skip_action(self):
        d = _decision(action="SKIP", rank=None, allocation_score=None)
        assert d.action == "SKIP"
        assert d.allocation_score is None

    def test_non_tradable_skip_example(self):
        d = _decision(action="SKIP", market_quality="BAD")
        assert d.market_quality == "BAD"
        assert d.market_quality in NON_TRADABLE_QUALITIES


# ── Score formula sanity tests ────────────────────────────────────────────────

class TestScoreFormula:
    """
    Verifies the composite score formula produces expected results.
    Formula: opp*0.40 + mq*0.30 + conf*0.20 + spread*0.10
    """

    def test_all_100_gives_100(self):
        score = (
            100.0 * W_OPPORTUNITY
            + 100.0 * W_MARKET_QUALITY
            + 100.0 * W_CONFIDENCE
            + 100.0 * W_SPREAD
        )
        assert abs(score - 100.0) < 0.001

    def test_all_zero_gives_zero(self):
        score = 0.0 * W_OPPORTUNITY + 0.0 * W_MARKET_QUALITY + 0.0 * W_CONFIDENCE + 0.0 * W_SPREAD
        assert abs(score) < 0.001

    def test_opportunity_dominates_weight(self):
        # Opportunity has highest weight (0.40)
        score_high_opp = 100.0 * W_OPPORTUNITY + 50.0 * W_MARKET_QUALITY + 50.0 * W_CONFIDENCE + 50.0 * W_SPREAD
        score_low_opp  =   0.0 * W_OPPORTUNITY + 50.0 * W_MARKET_QUALITY + 50.0 * W_CONFIDENCE + 50.0 * W_SPREAD
        assert score_high_opp > score_low_opp
        # Difference equals W_OPPORTUNITY * 100
        assert abs(score_high_opp - score_low_opp - W_OPPORTUNITY * 100.0) < 0.001


# ── Service instantiation ─────────────────────────────────────────────────────

class TestServiceSetup:
    def test_can_instantiate(self):
        svc = _make_svc()
        assert svc is not None

    def test_has_allocate_method(self):
        svc = _make_svc()
        assert hasattr(svc, "allocate")

    def test_has_get_ranked_summary_method(self):
        svc = _make_svc()
        assert hasattr(svc, "get_ranked_summary")
