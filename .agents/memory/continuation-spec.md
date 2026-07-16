---
name: Continuation Spec — Priorities 1-5
description: Implementation details for the 5 continuation priorities built after Decision Engine Intelligence Upgrade (Phases 1-8).
---

## What was built

**Priority 1 — Outcome Learning + Priority 5 — Feedback Loop**
- `outcome_learnings` table: one row per expired condition_id (UPSERT).
- `OutcomeLearningService.run()` — finds markets with `end_time < now`, looks up last `decision_log` WITH `created_at <= market.end_time` constraint (critical: prevents look-ahead error), finds any CLOSED position for that market.
- `correct = (realized_pnl > 0)` if position exists; else `correct = None`.
- Evaluates calibration (OVERCONFIDENT / UNDERCONFIDENT / WELL_CALIBRATED), entry quality (GOOD_FILTER / FALSE_POSITIVE / MISSED), consensus (RELIABLE / CONFLICTED_AND_WRONG / CONFLICTED_AND_LUCKY).
- Triggers `EnginePerformanceService.recompute_from_all_outcomes()` after each batch.

**Priority 2 — Engine Performance Tracking**
- `engine_performance_stats` table: one row per engine name (UPSERT).
- `EnginePerformanceService`: reads all outcome_learnings, tallies per-engine wins/losses using `_engine_was_correct()`.
- An engine is "correct" when its direction agreed with the winning side (not just with the AI).
- `ENGINE_DIRECTION_MAP`: 5 engines tracked: opportunity, orderbook, momentum, trend, funding.

**Priority 3 — Dynamic Engine Weights**
- `engine_weights` table: one row per engine (UPSERT).
- `DynamicWeightService`: accuracy-based adjustment ±30% from base weight, clamped to [min, max].
- Formula: `new_weight = base * (1 + (accuracy/100 - 0.5) * 2 * 0.30)`
- Only adjusts engines with ≥ `DYNAMIC_WEIGHT_MIN_OUTCOMES` (default 10) evaluated outcomes.
- `DecisionEngine._load_effective_weights(session)` — reads from DB at start of every `decide()` cycle, falls back to hardcoded constants if DB is empty.
- Decision Engine uses `self._current_weights.get("engine", WEIGHT_ENGINE)` in all 5 vote calculations.

**Priority 4 — Portfolio Allocation Intelligence**
- `PortfolioAllocationService.allocate(session, max_concurrent, min_score)` — ranks all Opportunity rows.
- Composite score: `opp_score * 0.40 + market_score * 0.30 + confidence * 0.20 + spread_tight * 0.10`
- Gate order: NON_TRADABLE_QUALITY → asset_already_open → condition_id_already_open → score < min → capacity full → ENTER.
- MarketQualityScore fields: `market_score` (not `quality_score`), `market_quality` (not `quality_label`), `computed_at` (not `evaluated_at`).

**Priority 5 — Feedback Loop**
- Integrated into OutcomeLearningService (not a separate service).
- 3 evaluators: `_evaluate_confidence()`, `_evaluate_entry_quality()`, `_evaluate_consensus()`.
- Results stored in `outcome_learnings` columns: `confidence_calibration`, `entry_quality_evaluation`, `consensus_evaluation`, `feedback_summary`.

## API endpoints
- `GET /api/v1/outcome-learning` — recent outcomes
- `GET /api/v1/outcome-learning/stats` — accuracy + calibration stats
- `GET /api/v1/outcome-learning/{condition_id}` — single market outcome
- `GET /api/v1/engine-performance` — all engines ranked by accuracy
- `GET /api/v1/engine-weights` — current weights vs base
- `GET /api/v1/engine-weights/effective` — effective weight dict for DecisionEngine
- `GET /api/v1/portfolio-allocation?max_concurrent=10&min_score=30` — ranked ENTER/DEFER/SKIP

## Background workers
- `run_outcome_learning_loop()` — every 300s (5 min), OUTCOME_LEARNING_ENABLED
- `run_dynamic_weight_loop()` — every 1800s (30 min), DYNAMIC_WEIGHT_ENABLED, RUN_ON_STARTUP=False

## Key design rules
- `created_at <= market.end_time` constraint on decision_log query is CRITICAL (prevents look-ahead).
- Outcome learning skips markets with no decision_log before expiry (no prediction → no evaluation).
- Dynamic weights require MIN_OUTCOMES=10 before adjusting (avoid noise from small samples).
- `_current_weights` is an instance attribute set once per `decide()` cycle (not per-market).
