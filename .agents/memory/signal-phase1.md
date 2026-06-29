---
name: AI Signal Engine Phase 1
description: Confidence scoring, market regime detection, MTF confirmation, signal ranking — design decisions and calibration values.
---

# AI Signal Engine Phase 1

## What was built
- `services/signal_confidence.py` — pure functions: `compute_confidence()` and `detect_regime()`
- 3 new columns on `signals` table: `confidence_score DOUBLE PRECISION`, `regime VARCHAR(16)`, `mtf_confirmed BOOLEAN`
- `repositories/signal_repository.py` — added `get_ranked_signals()`, `get_recent_signals_by_asset()`
- `services/signal_engine.py` — integrated confidence, regime, MTF per scan cycle
- `api/v1/signals.py` — added `GET /signals/ranked` endpoint + enriched `/stats`
- `services/strategy_engine.py` — signal confidence gate before OPEN_LONG decisions
- `tests/test_signal_phase1.py` — 30 unit + regression tests, all pass

## Calibration values (do not change without re-running tests)
- `_MAX_DEVIATION = 0.10` (was 0.15 — needed for SEED_DEVIATION HIGH to reach >=70 confidence)
- `_MAX_DELTA = 0.05` for MID_MOVE magnitude bonus
- `CONFIDENCE_HIGH = 70`, `CONFIDENCE_MEDIUM = 40`
- Strategy gate: `MIN_SIGNAL_CONFIDENCE = 25.0`, `MIN_SIGNAL_CONFIDENCE_MTF = 15.0`

**Why:** `_MAX_DEVIATION=0.10` ensures that a deviation of 0.08 (80% of max) scores above the HIGH tier threshold of 70. At 0.15, it only reaches 66. Also ensures SEED_DEVIATION ranks strictly above MID_MOVE at equal magnitude.

## Regime thresholds
- `RANGING_THRESHOLD = 0.005` (avg deviation from seed)
- `TREND_THRESHOLD = 0.010` (first-half vs second-half mean difference)
- `VOLATILE_THRESHOLD = 0.0001` (variance)
- Regime values: `RANGING | TRENDING_UP | TRENDING_DOWN | VOLATILE | UNKNOWN`

## MTF Confirmation logic
- After all markets in a cycle are scanned, group emitted signals by asset
- If ≥2 timeframes emitted signals in this cycle OR have signals in DB within 300s → `mtf_confirmed = True`
- MTF confirmation check is non-fatal: if DB query fails, cycle signals remain `mtf_confirmed=False`

## pytest runner path
Use `/home/runner/workspace/.pythonlibs/bin/pytest` (not `python -m pytest`) from `backend/` directory.
