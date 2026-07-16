"""
Tests — EnginePerformanceService (Priority 2).

Uses pure-Python mocks — no database, no async.
"""

from __future__ import annotations

import pytest

from app.services.engine_performance_service import (
    ENGINE_DIRECTION_MAP,
    _engine_was_correct,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeOutcome:
    """Minimal mock of an OutcomeLearning row."""
    def __init__(
        self,
        prediction: str,
        correct,
        opportunity_direction=None,
        orderbook_direction=None,
        momentum_direction=None,
        trend_direction=None,
        funding_direction=None,
        confidence=None,
    ):
        self.prediction             = prediction
        self.correct                = correct
        self.opportunity_direction  = opportunity_direction
        self.orderbook_direction    = orderbook_direction
        self.momentum_direction     = momentum_direction
        self.trend_direction        = trend_direction
        self.funding_direction      = funding_direction
        self.confidence             = confidence


# ── ENGINE_DIRECTION_MAP coverage ────────────────────────────────────────────

class TestEngineDirectionMap:
    def test_all_five_engines_registered(self):
        assert set(ENGINE_DIRECTION_MAP.keys()) == {
            "opportunity", "orderbook", "momentum", "trend", "funding"
        }

    def test_opportunity_uses_correct_field(self):
        field, bullish, bearish = ENGINE_DIRECTION_MAP["opportunity"]
        assert field == "opportunity_direction"
        assert "BUY_YES" in bullish
        assert "BUY_NO" in bearish

    def test_trend_uses_up_down(self):
        field, bullish, bearish = ENGINE_DIRECTION_MAP["trend"]
        assert "UP" in bullish
        assert "DOWN" in bearish


# ── _engine_was_correct unit tests ───────────────────────────────────────────

class TestEngineWasCorrect:
    # Opportunity engine
    def test_opportunity_buy_yes_correct(self):
        row = _FakeOutcome("BUY_YES", True, opportunity_direction="BUY_YES")
        assert _engine_was_correct("opportunity", row) is True

    def test_opportunity_buy_yes_wrong(self):
        row = _FakeOutcome("BUY_YES", False, opportunity_direction="BUY_YES")
        assert _engine_was_correct("opportunity", row) is False

    def test_opportunity_buy_no_correct(self):
        row = _FakeOutcome("BUY_NO", True, opportunity_direction="BUY_NO")
        assert _engine_was_correct("opportunity", row) is True

    def test_opportunity_neutral_returns_none(self):
        row = _FakeOutcome("BUY_YES", True, opportunity_direction="NEUTRAL")
        assert _engine_was_correct("opportunity", row) is None

    # Orderbook engine
    def test_orderbook_bullish_buy_yes_correct(self):
        row = _FakeOutcome("BUY_YES", True, orderbook_direction="BULLISH")
        assert _engine_was_correct("orderbook", row) is True

    def test_orderbook_bullish_buy_yes_wrong(self):
        row = _FakeOutcome("BUY_YES", False, orderbook_direction="BULLISH")
        assert _engine_was_correct("orderbook", row) is False

    def test_orderbook_bearish_buy_no_correct(self):
        row = _FakeOutcome("BUY_NO", True, orderbook_direction="BEARISH")
        assert _engine_was_correct("orderbook", row) is True

    def test_orderbook_bearish_disagreed_with_wrong_ai(self):
        # AI said BUY_YES and was wrong — orderbook said BEARISH (disagreed) → engine was right
        row = _FakeOutcome("BUY_YES", False, orderbook_direction="BEARISH")
        assert _engine_was_correct("orderbook", row) is True

    # Momentum engine
    def test_momentum_bullish_buy_yes_correct(self):
        row = _FakeOutcome("BUY_YES", True, momentum_direction="BULLISH")
        assert _engine_was_correct("momentum", row) is True

    def test_momentum_bearish_buy_yes_wrong(self):
        row = _FakeOutcome("BUY_YES", False, momentum_direction="BEARISH")
        assert _engine_was_correct("momentum", row) is True  # disagreed with wrong AI

    # Trend engine
    def test_trend_up_buy_yes_correct(self):
        row = _FakeOutcome("BUY_YES", True, trend_direction="UP")
        assert _engine_was_correct("trend", row) is True

    def test_trend_down_buy_yes_wrong(self):
        row = _FakeOutcome("BUY_YES", False, trend_direction="DOWN")
        assert _engine_was_correct("trend", row) is True  # disagreed with wrong AI

    # Funding engine
    def test_funding_bullish_buy_yes_correct(self):
        row = _FakeOutcome("BUY_YES", True, funding_direction="BULLISH")
        assert _engine_was_correct("funding", row) is True

    # Edge cases
    def test_missing_direction_returns_none(self):
        row = _FakeOutcome("BUY_YES", True, orderbook_direction=None)
        assert _engine_was_correct("orderbook", row) is None

    def test_wait_prediction_returns_none(self):
        row = _FakeOutcome("WAIT", True, orderbook_direction="BULLISH")
        assert _engine_was_correct("orderbook", row) is None

    def test_correct_none_returns_none(self):
        row = _FakeOutcome("BUY_YES", None, orderbook_direction="BULLISH")
        assert _engine_was_correct("orderbook", row) is None

    def test_unknown_engine_returns_none(self):
        row = _FakeOutcome("BUY_YES", True)
        assert _engine_was_correct("nonexistent_engine", row) is None
