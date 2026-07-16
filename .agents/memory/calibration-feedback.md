---
name: Calibration feedback loop (Phase 7 first increment)
description: DecisionEngine now reads historical calibration data and adjusts confidence forward — how it works, key constants, and what to extend next.
---

## What was built

`DecisionEngine._apply_calibration_adjustment` — static method added in Phase 7.

Called in `_decide_market()` as **Phase 4b**, immediately after the existing Phase 4
confidence computation. The adjusted value replaces `overall_confidence` for all
downstream gates (min confidence check, decision logging, reasons chain).

## Algorithm

1. Require `_MIN_TOTAL_EVALUATED=10` outcomes globally before applying any correction.
2. Find the `ConfidenceBucketStat` row that covers `raw_confidence` (5%-wide buckets).
3. Require `_MIN_CALIBRATION_SAMPLES=5` samples in that bucket.
4. `signed_error = accuracy − avg_confidence`
   - Positive → system was UNDERCONFIDENT → boost
   - Negative → system was OVERCONFIDENT → dampen
5. `adjustment = signed_error × _CORRECTION_FRACTION(0.25)`, capped at `±_MAX_ADJUSTMENT(15 pts)`
6. **Fallback** (no bucket with enough samples): if `overconfident_pct > 60%` → global 5%
   dampen; if `underconfident_pct > 60%` → global 5% boost; otherwise → no-op.
7. Result and explanation are returned; explanation is appended to `reasons` text in
   `decision_logs`. No new DB column (by design for Phase 7; add one later if needed).

## Key constants (class-level on DecisionEngine)

```python
_MIN_CALIBRATION_SAMPLES = 5
_MIN_TOTAL_EVALUATED     = 10
_CORRECTION_FRACTION     = 0.25
_MAX_ADJUSTMENT          = 15.0
```

**Why:** Conservative defaults — the system must have seen enough outcomes before
adjusting, and corrections are partial (25%) to avoid instability from small samples.

## How to apply

- Feed runs when `ConfidenceCalibrationService.recompute()` completes after every
  `OutcomeLearningService` batch (every 300s background loop).
- The next `DecisionEngine.decide()` call will automatically read the updated buckets.
- To tune aggressiveness: raise `_CORRECTION_FRACTION` (up to 0.5 is reasonable) or
  lower `_MIN_CALIBRATION_SAMPLES`/`_MIN_TOTAL_EVALUATED`.

## Tests

`backend/app/tests/test_confidence_calibration_feedback.py` — 41 pure-Python tests.
No DB. No live engines. Covers: no-data guard, bucket correction, global fallback,
bounds enforcement, bucket selection edge cases, boundary values (50.0, 100.0), and
fallback note formatting (closing parenthesis regression fixed by code review).

## Known reviewer note

The fallback message used a conditional f-string expression inside a tuple that parsed
correctly but produced a missing `)` in the `well_calibrated_pct` branch. Fixed by
restructuring as an if/else block. Test class `TestFallbackNoteFormatting` covers this.
