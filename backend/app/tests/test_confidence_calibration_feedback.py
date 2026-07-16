"""
Tests — DecisionEngine._apply_calibration_adjustment (Phase 7 — Historical Database).

Confidence feedback loop: the engine adjusts its raw confidence score using
historical calibration data (bucket-level accuracy vs avg_confidence) so that
systematic over/underconfidence is corrected forward.

Uses pure-Python mock objects. No database. No live engines.
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from typing import Optional

from app.services.decision_engine import DecisionEngine


# ── Shared constants (mirrors DecisionEngine class attributes) ─────────────────

MIN_BUCKET  = DecisionEngine._MIN_CALIBRATION_SAMPLES
MIN_TOTAL   = DecisionEngine._MIN_TOTAL_EVALUATED
CORR_FRAC   = DecisionEngine._CORRECTION_FRACTION
MAX_ADJ     = DecisionEngine._MAX_ADJUSTMENT


# ── Minimal mock objects ───────────────────────────────────────────────────────

@dataclass
class MockSummary:
    total_evaluated:    int
    overconfident_pct:  Optional[float] = None
    underconfident_pct: Optional[float] = None
    well_calibrated_pct:Optional[float] = None


@dataclass
class MockBucket:
    bucket_min:   float
    bucket_max:   float
    sample_count: int
    accuracy:     Optional[float]
    avg_confidence: Optional[float]


def _call(
    raw: float,
    summary: Optional[MockSummary],
    buckets: list[MockBucket],
) -> tuple[float, str]:
    return DecisionEngine._apply_calibration_adjustment(
        raw, summary, buckets,
        min_bucket_samples  = MIN_BUCKET,
        min_total_evaluated = MIN_TOTAL,
        correction_fraction = CORR_FRAC,
        max_adjustment      = MAX_ADJ,
    )


# ── No data / insufficient data ────────────────────────────────────────────────

class TestNoData:
    def test_none_summary_returns_unchanged(self):
        conf, note = _call(70.0, None, [])
        assert conf == 70.0
        assert note == ""

    def test_summary_below_min_total_returns_unchanged(self):
        summary = MockSummary(total_evaluated=5)  # < MIN_TOTAL (10)
        conf, note = _call(70.0, summary, [])
        assert conf == 70.0
        assert "no adjustment yet" in note

    def test_zero_total_evaluated_returns_unchanged(self):
        summary = MockSummary(total_evaluated=0)
        conf, note = _call(65.0, summary, [])
        assert conf == 65.0
        assert "no adjustment yet" in note


# ── Bucket-level correction: OVERCONFIDENT (dampen) ───────────────────────────

class TestBucketOverconfident:
    """accuracy < avg_confidence → system claimed higher confidence than accuracy warrants."""

    def _summary(self) -> MockSummary:
        return MockSummary(total_evaluated=50)

    def _bucket(self, bmin, bmax, accuracy, avg_conf, n=20) -> MockBucket:
        return MockBucket(bmin, bmax, n, accuracy, avg_conf)

    def test_overconfident_bucket_dampens(self):
        # Raw 75%, bucket shows 55% accuracy at avg_conf 75% → error = 55-75 = -20
        # adjustment = -20 * 0.25 = -5.0
        bucket = self._bucket(70.0, 75.0, accuracy=55.0, avg_conf=75.0)
        conf, note = _call(72.0, self._summary(), [bucket])
        assert conf < 72.0
        assert "dampened" in note

    def test_overconfident_70pct_bucket_exact_adjustment(self):
        # signed_error = 60 - 80 = -20, adjustment = -20 * 0.25 = -5.0
        bucket = self._bucket(75.0, 80.0, accuracy=60.0, avg_conf=80.0)
        conf, note = _call(77.0, self._summary(), [bucket])
        assert abs(conf - (77.0 - 5.0)) < 0.01
        assert "dampened" in note

    def test_adjustment_capped_at_max_adjustment(self):
        # signed_error = 0 - 100 = -100, adjustment = -100 * 0.25 = -25 → capped at -15
        bucket = self._bucket(95.0, 100.0, accuracy=0.0, avg_conf=100.0)
        conf, note = _call(98.0, self._summary(), [bucket])
        assert conf == 98.0 - MAX_ADJ  # capped
        assert "dampened" in note

    def test_overconfident_note_contains_bucket_range(self):
        bucket = self._bucket(65.0, 70.0, accuracy=50.0, avg_conf=70.0)
        _, note = _call(67.0, self._summary(), [bucket])
        assert "65" in note and "70" in note


# ── Bucket-level correction: UNDERCONFIDENT (boost) ───────────────────────────

class TestBucketUnderconfident:
    """accuracy > avg_confidence → system was more correct than its confidence implied."""

    def _summary(self) -> MockSummary:
        return MockSummary(total_evaluated=30)

    def _bucket(self, bmin, bmax, accuracy, avg_conf, n=15) -> MockBucket:
        return MockBucket(bmin, bmax, n, accuracy, avg_conf)

    def test_underconfident_bucket_boosts(self):
        # accuracy=80%, avg_conf=60% → signed_error=+20, adjustment=+5.0
        bucket = self._bucket(55.0, 60.0, accuracy=80.0, avg_conf=60.0)
        conf, note = _call(57.0, self._summary(), [bucket])
        assert conf > 57.0
        assert "boosted" in note

    def test_underconfident_exact_adjustment(self):
        # signed_error = 80 - 60 = +20, adjustment = +20 * 0.25 = +5.0
        bucket = self._bucket(55.0, 60.0, accuracy=80.0, avg_conf=60.0)
        conf, note = _call(57.0, self._summary(), [bucket])
        assert abs(conf - (57.0 + 5.0)) < 0.01

    def test_boost_capped_at_max_adjustment(self):
        # signed_error = 100 - 0 = 100, adjustment = +25 → capped at +15
        bucket = self._bucket(50.0, 55.0, accuracy=100.0, avg_conf=0.0)
        conf, note = _call(52.0, self._summary(), [bucket])
        assert conf == 52.0 + MAX_ADJ
        assert "boosted" in note

    def test_boost_does_not_exceed_100(self):
        bucket = self._bucket(95.0, 100.0, accuracy=100.0, avg_conf=90.0)
        conf, _ = _call(99.0, self._summary(), [bucket])
        assert conf <= 100.0


# ── Well-calibrated bucket (unchanged) ────────────────────────────────────────

class TestBucketWellCalibrated:
    def test_zero_signed_error_unchanged(self):
        summary = MockSummary(total_evaluated=40)
        bucket  = MockBucket(65.0, 70.0, 20, accuracy=67.5, avg_confidence=67.5)
        conf, note = _call(68.0, summary, [bucket])
        assert conf == 68.0
        assert "unchanged" in note

    def test_tiny_error_within_rounding_unchanged(self):
        # signed_error = 68.1 - 68.0 = 0.1, adjustment = 0.1 * 0.25 = 0.025 → rounds to 0.03
        summary = MockSummary(total_evaluated=20)
        bucket  = MockBucket(65.0, 70.0, 10, accuracy=68.1, avg_confidence=68.0)
        conf, note = _call(68.0, summary, [bucket])
        # The adjustment is < 0.05 → still "unchanged" label
        assert "unchanged" in note


# ── Below-50 catch-all bucket ─────────────────────────────────────────────────

class TestBelow50Bucket:
    def test_below50_bucket_applied_for_low_confidence(self):
        summary = MockSummary(total_evaluated=25)
        # below-50 catch-all bucket (bucket_max <= 50)
        bucket  = MockBucket(0.0, 50.0, 10, accuracy=60.0, avg_confidence=35.0)
        conf, note = _call(38.0, summary, [bucket])
        # signed_error = 60 - 35 = 25, adjustment = 25 * 0.25 = 6.25 → boosted
        assert conf > 38.0
        assert "boosted" in note

    def test_below50_bucket_not_applied_for_high_confidence(self):
        summary = MockSummary(total_evaluated=25)
        bucket  = MockBucket(0.0, 50.0, 10, accuracy=60.0, avg_confidence=35.0)
        # raw=75 → not below 50 → bucket should not match
        conf, note = _call(75.0, summary, [bucket])
        # No matching bucket → falls to global fallback or no-op
        assert conf == 75.0 or "Global" in note or note == ""


# ── Insufficient bucket samples (fall through to global) ──────────────────────

class TestInsufficientBucketSamples:
    def test_bucket_below_min_samples_is_skipped(self):
        summary = MockSummary(total_evaluated=30, overconfident_pct=30.0,
                              underconfident_pct=20.0, well_calibrated_pct=50.0)
        bucket  = MockBucket(65.0, 70.0, sample_count=2, accuracy=40.0, avg_confidence=70.0)
        # bucket has only 2 samples < MIN_BUCKET(5) → should not apply bucket correction
        conf, note = _call(67.0, summary, [bucket])
        # no dominant global bias → no adjustment
        assert conf == 67.0

    def test_empty_bucket_list_with_well_calibrated_summary_no_adjustment(self):
        summary = MockSummary(total_evaluated=15, overconfident_pct=20.0,
                              underconfident_pct=15.0, well_calibrated_pct=65.0)
        conf, _ = _call(68.0, summary, [])
        assert conf == 68.0


# ── Global fallback: dominant overconfidence bias ─────────────────────────────

class TestGlobalFallbackOverconfident:
    def test_dominant_overconfidence_applies_global_dampen(self):
        # >60% overconfident → apply 5% global dampen
        summary = MockSummary(total_evaluated=50, overconfident_pct=70.0,
                              underconfident_pct=10.0, well_calibrated_pct=20.0)
        conf, note = _call(80.0, summary, [])
        # expected: 80 - (80 * 0.05) = 80 - 4 = 76
        assert conf < 80.0
        assert "OVERCONFIDENT" in note

    def test_dominant_overconfidence_global_adjustment_capped(self):
        # Very high confidence: 80 * 0.05 = 4.0 < MAX_ADJ(15)
        summary = MockSummary(total_evaluated=100, overconfident_pct=65.0)
        conf, note = _call(80.0, summary, [])
        assert abs(conf - (80.0 - 80.0 * 0.05)) < 0.01

    def test_borderline_overconfidence_below_threshold_no_global_adjust(self):
        # 60.0% is exactly the threshold — not strictly greater than
        summary = MockSummary(total_evaluated=50, overconfident_pct=60.0)
        conf, _ = _call(75.0, summary, [])
        assert conf == 75.0


# ── Global fallback: dominant underconfidence bias ────────────────────────────

class TestGlobalFallbackUnderconfident:
    def test_dominant_underconfidence_boosts(self):
        summary = MockSummary(total_evaluated=50, overconfident_pct=5.0,
                              underconfident_pct=70.0, well_calibrated_pct=25.0)
        conf, note = _call(55.0, summary, [])
        # 55 * 0.05 = 2.75 boost
        assert conf > 55.0
        assert "UNDERCONFIDENT" in note

    def test_boost_does_not_exceed_100(self):
        summary = MockSummary(total_evaluated=50, underconfident_pct=80.0)
        conf, _ = _call(99.0, summary, [])
        assert conf <= 100.0


# ── Confidence bounds never violated ──────────────────────────────────────────

class TestConfidenceBounds:
    """Adjusted confidence must always stay in [0.0, 100.0]."""

    def test_confidence_never_goes_negative(self):
        summary = MockSummary(total_evaluated=50, overconfident_pct=75.0)
        bucket  = MockBucket(0.0, 50.0, 20, accuracy=0.0, avg_confidence=50.0)
        conf, _ = _call(1.0, summary, [bucket])
        assert conf >= 0.0

    def test_confidence_never_exceeds_100(self):
        summary = MockSummary(total_evaluated=50, underconfident_pct=75.0)
        bucket  = MockBucket(95.0, 100.0, 20, accuracy=100.0, avg_confidence=50.0)
        conf, _ = _call(99.0, summary, [bucket])
        assert conf <= 100.0

    def test_zero_raw_confidence_no_negative_result(self):
        summary = MockSummary(total_evaluated=20)
        bucket  = MockBucket(0.0, 50.0, 10, accuracy=0.0, avg_confidence=40.0)
        conf, _ = _call(0.0, summary, [bucket])
        assert conf >= 0.0

    def test_100_raw_confidence_no_overshoot(self):
        summary = MockSummary(total_evaluated=20)
        bucket  = MockBucket(95.0, 100.0, 10, accuracy=100.0, avg_confidence=95.0)
        conf, _ = _call(100.0, summary, [bucket])
        assert conf <= 100.0


# ── Multiple buckets: correct one is selected ─────────────────────────────────

class TestBucketSelection:
    def _summary(self) -> MockSummary:
        return MockSummary(total_evaluated=40)

    def test_selects_correct_bucket_by_raw_confidence(self):
        buckets = [
            MockBucket(50.0, 55.0, 10, accuracy=40.0, avg_confidence=52.0),  # overconf
            MockBucket(65.0, 70.0, 10, accuracy=80.0, avg_confidence=67.0),  # underconf
            MockBucket(70.0, 75.0, 10, accuracy=72.0, avg_confidence=72.0),  # calibrated
        ]
        # raw=68 → should use bucket [65,70]: accuracy=80, avg=67 → boosted
        conf, note = _call(68.0, self._summary(), buckets)
        assert conf > 68.0
        assert "65" in note and "70" in note

    def test_selects_correct_bucket_low_range(self):
        buckets = [
            MockBucket(50.0, 55.0, 10, accuracy=40.0, avg_confidence=52.0),  # overconf
            MockBucket(65.0, 70.0, 10, accuracy=80.0, avg_confidence=67.0),
        ]
        # raw=52 → bucket [50, 55]: accuracy=40, avg_conf=52 → dampened
        conf, note = _call(52.0, self._summary(), buckets)
        assert conf < 52.0
        assert "dampened" in note

    def test_no_matching_bucket_falls_to_global_or_noop(self):
        # Buckets that don't cover raw_confidence=90.0
        buckets = [
            MockBucket(50.0, 55.0, 10, accuracy=50.0, avg_confidence=52.0),
            MockBucket(55.0, 60.0, 10, accuracy=60.0, avg_confidence=57.0),
        ]
        summary = MockSummary(total_evaluated=20)
        conf, _ = _call(90.0, summary, buckets)
        # No matching bucket and no dominant global bias → unchanged
        assert conf == 90.0


# ── Boundary: raw_confidence exactly at 50.0 and 100.0 ───────────────────────

class TestBoundaryConfidenceValues:
    """Edge cases at the exact bucket boundaries."""

    def _summary(self) -> MockSummary:
        return MockSummary(total_evaluated=30)

    def test_raw_confidence_exactly_50_uses_above50_bucket(self):
        # 50.0 is NOT below 50 (strict <), so the below-50 catch-all should not match.
        # It should fall into the [50.0, 55.0) bucket instead.
        buckets = [
            MockBucket(0.0,  50.0, 10, accuracy=30.0, avg_confidence=40.0),  # catch-all (should NOT match)
            MockBucket(50.0, 55.0, 10, accuracy=70.0, avg_confidence=52.0),  # SHOULD match
        ]
        conf, note = _call(50.0, self._summary(), buckets)
        # signed_error = 70 - 52 = 18, adjustment = 18 * 0.25 = 4.5 → boosted
        assert conf > 50.0
        assert "50" in note and "55" in note

    def test_raw_confidence_exactly_100_uses_top_bucket(self):
        # The top bucket (bucket_max == 100.0) must include the exact value 100.0.
        buckets = [
            MockBucket(95.0, 100.0, 10, accuracy=90.0, avg_confidence=97.0),
        ]
        conf, note = _call(100.0, self._summary(), buckets)
        # signed_error = 90 - 97 = -7, adjustment = -7 * 0.25 = -1.75 → dampened
        assert conf < 100.0
        assert "dampened" in note

    def test_raw_confidence_just_below_50_uses_catch_all_bucket(self):
        buckets = [
            MockBucket(0.0,  50.0, 10, accuracy=65.0, avg_confidence=40.0),  # SHOULD match
            MockBucket(50.0, 55.0, 10, accuracy=60.0, avg_confidence=52.0),
        ]
        conf, note = _call(49.9, self._summary(), buckets)
        # Uses catch-all bucket: signed_error = 65 - 40 = 25, adjustment = 6.25 → boosted
        assert conf > 49.9
        assert "boosted" in note

    def test_raw_confidence_99_uses_95_100_bucket(self):
        buckets = [
            MockBucket(90.0,  95.0, 10, accuracy=80.0, avg_confidence=92.0),
            MockBucket(95.0, 100.0, 10, accuracy=90.0, avg_confidence=97.0),
        ]
        conf, note = _call(99.0, self._summary(), buckets)
        # 99.0 is in [95,100) → uses second bucket
        assert "95" in note and "100" in note


# ── Fallback note formatting ──────────────────────────────────────────────────

class TestFallbackNoteFormatting:
    """The fallback note (insufficient samples, no dominant global bias) must
    always be a complete, parseable string with no missing parentheses."""

    def _call_fallback(self, well_calibrated_pct=None) -> str:
        summary = MockSummary(
            total_evaluated=15,
            overconfident_pct=20.0,
            underconfident_pct=20.0,
            well_calibrated_pct=well_calibrated_pct,
        )
        # Use a bucket with insufficient samples so we fall through to the fallback note
        bucket = MockBucket(65.0, 70.0, sample_count=2, accuracy=60.0, avg_confidence=67.0)
        _, note = _call(67.0, summary, [bucket])
        return note

    def test_fallback_note_with_well_calibrated_pct_has_closing_paren(self):
        note = self._call_fallback(well_calibrated_pct=60.0)
        assert note.endswith(")")
        assert "well_calibrated=60%" in note
        assert "total evaluated=15" in note

    def test_fallback_note_without_well_calibrated_pct_has_closing_paren(self):
        note = self._call_fallback(well_calibrated_pct=None)
        assert note.endswith(")")
        assert "total evaluated=15" in note

    def test_fallback_note_contains_total_evaluated(self):
        note = self._call_fallback(well_calibrated_pct=50.0)
        assert "total evaluated" in note

    def test_fallback_note_zero_well_calibrated(self):
        note = self._call_fallback(well_calibrated_pct=0.0)
        assert "well_calibrated=0%" in note
        assert note.endswith(")")

    def test_fallback_note_is_nonempty_string(self):
        note = self._call_fallback()
        assert isinstance(note, str) and len(note) > 0


# ── Method is a class-level static callable ───────────────────────────────────

class TestMethodAvailability:
    def test_static_method_callable(self):
        assert callable(DecisionEngine._apply_calibration_adjustment)

    def test_returns_tuple_of_float_and_str(self):
        summary = MockSummary(total_evaluated=5)
        result  = _call(60.0, summary, [])
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], str)

    def test_constants_are_sane(self):
        assert 0 < MIN_BUCKET <= 20
        assert 0 < MIN_TOTAL  <= 50
        assert 0 < CORR_FRAC  < 1.0
        assert 5 <= MAX_ADJ   <= 30
