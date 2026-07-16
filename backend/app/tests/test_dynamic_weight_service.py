"""
Tests — DynamicWeightService (Priority 3).

Tests pure computation logic (no database, no async).
"""

from __future__ import annotations

import pytest

from app.models.engine_weight import BASE_WEIGHTS, WEIGHT_MAX, WEIGHT_MIN
from app.services.dynamic_weight_service import ADJUSTMENT_SCALE, _compute_new_weight


class TestComputeNewWeight:
    # ── Accuracy = 50% (random chance) ──────────────────────────────────────
    def test_fifty_pct_accuracy_returns_base_weight(self):
        for name, base in BASE_WEIGHTS.items():
            w, factor = _compute_new_weight(name, 50.0, 20)
            assert abs(w - base) < 0.001, f"{name}: expected base {base}, got {w}"

    def test_fifty_pct_factor_is_zero(self):
        _, factor = _compute_new_weight("opportunity", 50.0, 20)
        assert abs(factor) < 0.001

    # ── Accuracy = 100% ──────────────────────────────────────────────────────
    def test_hundred_pct_increases_weight(self):
        for name, base in BASE_WEIGHTS.items():
            w, _ = _compute_new_weight(name, 100.0, 20)
            assert w > base, f"{name}: expected increase above base {base}"

    def test_hundred_pct_bounded_by_max(self):
        for name in BASE_WEIGHTS:
            w, _ = _compute_new_weight(name, 100.0, 20)
            assert w <= WEIGHT_MAX[name], f"{name}: {w} exceeds max {WEIGHT_MAX[name]}"

    # ── Accuracy = 0% ────────────────────────────────────────────────────────
    def test_zero_pct_decreases_weight(self):
        for name, base in BASE_WEIGHTS.items():
            w, _ = _compute_new_weight(name, 0.0, 20)
            assert w < base, f"{name}: expected decrease below base {base}"

    def test_zero_pct_bounded_by_min(self):
        for name in BASE_WEIGHTS:
            w, _ = _compute_new_weight(name, 0.0, 20)
            assert w >= WEIGHT_MIN[name], f"{name}: {w} below min {WEIGHT_MIN[name]}"

    # ── Adjustment scale ─────────────────────────────────────────────────────
    def test_adjustment_scale_positive_at_100pct(self):
        _, factor = _compute_new_weight("opportunity", 100.0, 20)
        assert abs(factor - 1.0) < 0.001, f"Expected factor=1.0, got {factor}"

    def test_adjustment_scale_negative_at_0pct(self):
        _, factor = _compute_new_weight("opportunity", 0.0, 20)
        assert abs(factor - (-1.0)) < 0.001, f"Expected factor=-1.0, got {factor}"

    # ── Unknown engine falls back safely ─────────────────────────────────────
    def test_unknown_engine_uses_default_base(self):
        w, _ = _compute_new_weight("nonexistent", 75.0, 20)
        # Should not raise, uses hardcoded fallback base=0.10
        assert w > 0

    # ── Rounding ─────────────────────────────────────────────────────────────
    def test_output_rounded_to_4dp(self):
        w, factor = _compute_new_weight("opportunity", 73.0, 20)
        assert w == round(w, 4)
        assert factor == round(factor, 4)

    # ── All engines present in maps ─────────────────────────────────────────
    def test_all_base_engines_have_min_max(self):
        for name in BASE_WEIGHTS:
            assert name in WEIGHT_MIN, f"{name} missing from WEIGHT_MIN"
            assert name in WEIGHT_MAX, f"{name} missing from WEIGHT_MAX"

    def test_min_is_always_less_than_base(self):
        for name, base in BASE_WEIGHTS.items():
            assert WEIGHT_MIN[name] < base, f"{name}: min >= base"

    def test_max_is_always_greater_than_base(self):
        for name, base in BASE_WEIGHTS.items():
            assert WEIGHT_MAX[name] > base, f"{name}: max <= base"
