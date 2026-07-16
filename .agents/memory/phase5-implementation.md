---
name: Phase 5 Trade Evaluation & Replay
description: Phase 5 complete — TradeEvaluation model, 3 services, 3 routers, DB migration, 65 new tests (377→442)
---

# Phase 5: Trade Evaluation, Replay, Engine Scorecard

## What was built
- **TradeEvaluation model** (`models/trade_evaluation.py`) — new `trade_evaluations` table; unique on `position_id`
- **TradeEvaluationService** (`services/trade_evaluation_service.py`) — scores CLOSED positions 0-100 across 4 components (entry_quality, exit_quality, timing_score, pnl_efficiency); letter grade A-F
- **TradeReplayService** (`services/trade_replay_service.py`) — step-by-step timeline for any CLOSED position; flat dataset export
- **EngineScorecardService** (`services/engine_scorecard_service.py`) — 5 engine dimensions scored; composite grade; uses `opportunity_score` not `score` (Opportunity model field)
- **Schemas** (`schemas/evaluation.py`) — TradeEvaluationSchema, EvaluationSummaryResponse, EngineScorecardResponse, TradeReplayResponse, TradeDatasetResponse, TradesListResponse, TradeSummaryRow, GradeDistribution, ReplayEvent, EngineScoreEntry

## New API endpoints
- `GET /api/v1/trades` — paginated closed trades + evaluation
- `GET /api/v1/trades/{id}` — single trade
- `GET /api/v1/replay/{position_id}` — full replay timeline
- `GET /api/v1/replay/dataset` — flat dataset for ML
- `GET /api/v1/evaluation/summary` — aggregate quality stats
- `GET /api/v1/evaluation/scorecard` — engine scorecard
- `GET /api/v1/evaluation/grades` — grade distribution
- `GET /api/v1/evaluation/{position_id}` — single position evaluation
- `POST /api/v1/evaluation/run` — trigger evaluation of unevaluated positions

## DB migration
Phase 5 adds `trade_evaluations` table via `Base.metadata.create_all` (ORM-managed), plus 3 index migrations labeled `phase5_te_idx*` in `init_db()`.

## Tests
377 → 442 tests (65 new). All pass.

## Key gotchas
- Signal model fields: `yes_mid_before`, `yes_mid_after`, `yes_mid_delta` (NOT `previous_mid`/`current_mid`)
- Opportunity model: `opportunity_score` (NOT `score`)
- `evaluate_all()` is idempotent — skips already-evaluated positions
- `evaluate_position()` upserts by delete+insert on `position_id`
- Timing score peaks at hold==typical (15m for 5m, 45m for 15m, 180m for 1H)
- `pnl_efficiency` = realized / peak_pnl_usdc × 100 (not vs position size)
- Scorecard uses SQL subquery intersections for signal/opp accuracy — `min()` approach was wrong
- Both `func` AND `select` must be in top-level imports (not just a local `from sqlalchemy import func`)
- `get_evaluation_summary` uses SQL aggregates (AVG/GROUP BY) not Python iteration

**Why:** correctness of metrics required real set-intersection for scorecard, not min(A,B).
**How to apply:** For any "what fraction of X led to Y" metric, use subquery intersection by condition_id.
