# LIMWANPO AI — FINAL ARCHITECTURE DECISION
**Date:** 2026-07-07  
**Authority:** Phase 2 Architecture Audit  
**Status:** DECISION READY — awaiting implementation approval

---

## 1. CURRENT ARCHITECTURE STATE

LIMWANPO AI is a 16-layer backend pipeline with a single-page dashboard frontend.

### What it actually does

The system ingests binary prediction market data from Polymarket and price data from Binance, runs 9+ analytical engines to score each market's probability of outcome, generates probability verdicts, and tracks those verdicts against market resolutions to improve engine accuracy over time.

### What it calls itself

A trading bot. Every layer from 6 onward uses trading vocabulary: orders, positions, execution, risk, portfolio, PnL, stop-loss, capital. This vocabulary is skin-deep — it wraps a probability analysis core that has no live exchange connectivity, no wallet, and no real capital.

### Key structural facts (from audit evidence)

1. `clob_client.py` is read-only. Zero POST/PUT/DELETE methods exist. The system cannot submit orders to Polymarket.
2. All "execution" is local DB simulation. `ExecutionEngine` computes fill prices from internal snapshots and writes rows to the local `orders` table.
3. The feedback loop (Outcome Learning → Calibration → Dynamic Weights) currently requires closed paper positions to produce non-null `correct` values. This is the only structural link between the trading vocabulary and the intelligence core.
4. 12 of 12 frontend fetch() calls are to endpoints the system already owns. 5 of those 12 carry trading identity (portfolio/PnL/positions).
5. 27 trading identity terms were found across the codebase. None of them represent live exchange logic.

---

## 2. IDENTITY MISMATCH SUMMARY

| Layer | What it says | What it does |
|---|---|---|
| ExecutionEngine | "Executes trades" | Writes local DB rows, no external API |
| StrategyEngine | "Creates trade decisions" | Emits probability direction recommendations |
| RiskEngine | "Gates risk" | Deduplicates recommendations and limits coverage |
| PositionTrackingService | "Tracks positions + PnL" | Tracks probability drift over a recommendation's lifetime |
| ExitEngine | "Stop-loss / take-profit" | Closes recommendations at expiry or confidence drop |
| PortfolioService | "Portfolio management" | Aggregates prediction state and historical accuracy |
| CapitalManagementService | "Capital drawdown limits" | Should be: prediction budget limits |
| `orders` table | "Order fills" | Timestamped recommendation commits |
| `positions` table | "Open positions" | Active prediction records |
| `risk_events` table | "Risk events" | Quality gate rejections |
| `trade_decisions` table | "Trade decisions" | Recommendation queue |
| `realized_pnl` | "Realised profit/loss" | Resolution delta (exit probability − commit probability) |

**Root cause:** The trading vocabulary was correct when the system was designed as a trading bot. It has since evolved into a probability analysis platform while retaining the original naming scheme.

---

## 3. OPTION A vs OPTION B ANALYSIS

---

### OPTION A: Keep Layers 6–16, Rename Trading Concepts into Prediction Concepts

**Description:** All 16 layers are retained. Trading vocabulary is systematically replaced with probability-analysis vocabulary. The single structural coupling point (OutcomeLearning's `correct` field requiring a closed position) is redesigned to use direct Gamma API market resolution lookup.

#### Benefits
- Zero intelligence loss — every AI engine, weight system, calibration module, and outcome learner is preserved
- The feedback loop (Outcome → Calibration → Dynamic Weights → DecisionEngine) continues functioning and improving
- Minimal code change — primarily renaming, not redesign
- Dashboard remains functional with the same 12 fetch() calls (5 endpoint paths rename, data structure stays identical)
- All 55+ UNU endpoints remain available for future features or API consumers
- No DB migration required beyond column/table renames
- The system immediately presents as a probability analysis platform to any viewer

#### Risks
- Rename scope is broad: 27 terms × (models + repos + services + schemas + api + tests + UI) = significant surface area
- DB column renames require careful migration to preserve existing data
- `OutcomeLearningService` correctness logic redesign is a behavioural change, not just a rename

#### Data Loss
- **NONE** — all historical data is preserved through renames

#### Learning Impact
- **IMPROVED** after OutcomeLearningService redesign: correctness no longer depends on closed paper positions; market resolution fetched directly from Gamma API; every expired market produces a non-null `correct` value immediately

#### Outcome Learning Impact
- **IMPROVED** — decoupled from execution pipeline; learns from every market resolution regardless of whether a paper trade was simulated

#### Confidence Calibration Impact
- **IMPROVED** — more non-null `correct` rows feed the calibration buckets; ECE/ACE metrics become more reliable

#### Dynamic Weight Impact
- **IMPROVED** — more accurate per-engine accuracy data drives better weight optimisation

#### Performance Analytics Impact
- **TRANSFORMED** — replaces P&L/ROI metrics with accuracy rate, Brier score, calibration score; all existing analytics pipeline is preserved

---

### OPTION B: Remove Layers 6–16 Entirely

**Description:** StrategyEngine, RiskEngine, ExecutionEngine, PositionTrackingService, ExitEngine, PortfolioService and all associated models, repositories, tables and API endpoints are deleted.

#### Benefits
- Codebase is smaller and has no trading identity anywhere
- No renaming work required for the deleted layers

#### Risks
- **CATASTROPHIC DATA LOSS** for any system with historical paper trade records
- **BREAKS the feedback loop entirely** — OutcomeLearningService currently reads closed `positions` to determine `correct`. Without positions, every outcome row has `correct = NULL`. Calibration, Dynamic Weights, and Engine Performance stop updating permanently.
- 5 of 12 frontend fetch() calls break instantly (`/portfolio/pnl`, `/positions/open`, `/portfolio/summary`, `/analytics/performance`, `/analytics/capital`)
- The dashboard Portfolio panel, exposure display, and accuracy tracking go blank
- `decision_logs.risk_gated` field becomes permanently false (no RiskEngine to set it)
- All 55+ trading-related API endpoints disappear with no replacement
- The intelligence core (Layers 1–5) continues running but **stops improving** — it becomes a static scoring engine with no learning loop
- `TradeEvaluationService`, `TradeReplayService` lose all input data

#### Data Loss
- All `orders` records
- All `positions` records  
- All `risk_events` records
- All `trade_decisions` records
- All `trade_evaluations` records
- Historical `outcome_learnings.correct` values become meaningless (no position reference)
- `engine_weights` freeze — no new learning data

#### Learning Impact
- **DESTROYED** — the system loses the ability to learn from market resolutions

#### Outcome Learning Impact
- **BROKEN** — all new outcomes have `correct = NULL`; the service runs but produces no usable output

#### Confidence Calibration Impact
- **BROKEN** — zero new non-null rows; calibration freezes at its last computed state

#### Dynamic Weight Impact
- **FROZEN** — no new accuracy data; engine weights stagnate

#### Performance Analytics Impact
- **ELIMINATED** — no position or order data to compute from

---

### RECOMMENDATION: **OPTION A**

Option B destroys the learning system that makes LIMWANPO AI intelligent. The probability analysis capability of LIMWANPO AI is entirely preserved in Layers 1–5 and the learning stack (Layers 11–16), but those layers **depend on Layers 6–10 as their data source**. Removing the data-generating layers silences the intelligence. Option A achieves the identity transformation without sacrificing any capability.

---

## 4. COMPONENTS TO KEEP

*(No changes to logic or naming — pure probability infrastructure)*

| Component | File | Keep As-Is |
|---|---|---|
| MarketUniverseService | market_universe_service.py | ✓ |
| MarketPriceService | market_price_service.py | ✓ |
| clob_client.py | clob_client.py | ✓ |
| gamma_series_client.py | gamma_series_client.py | ✓ |
| binance_market_data.py | binance_market_data.py | ✓ |
| SignalEngine | signal_engine.py | ✓ |
| signal_confidence.py | signal_confidence.py | ✓ |
| MomentumEngine | momentum_engine.py | ✓ |
| TrendEngine | trend_engine.py | ✓ |
| VolatilityEngine | volatility_engine.py | ✓ |
| OrderbookEngine | orderbook_engine.py | ✓ |
| FundingEngine | funding_engine.py | ✓ |
| NewsEngine | news_engine.py | ✓ |
| PolymarketMarketEngine | polymarket_market_engine.py | ✓ |
| MarketContextEngine | market_context_engine.py | ✓ |
| MarketReferenceService | market_reference_service.py | ✓ |
| OpportunityEngine | opportunity_engine.py | ✓ |
| DecisionEngine | decision_engine.py | ✓ |
| _compute_consensus() | (embedded in decision_engine.py) | ✓ |
| ConfidenceCalibrationService | confidence_calibration_service.py | ✓ |
| DynamicWeightService | dynamic_weight_service.py | ✓ |
| EnginePerformanceService | engine_performance_service.py | ✓ |
| EngineScorecardService | engine_scorecard_service.py | ✓ |
| All score tables | signals, momentum_scores, trend_scores, volatility_scores, orderbook_scores, funding_scores, news_scores, market_quality_scores, market_context_scores, opportunities | ✓ |
| decision_logs table | (already probability-named) | ✓ |
| outcome_learnings table | (structure preserved; correctness source redesigned) | ✓ |
| engine_weights table | ✓ | ✓ |
| engine_performance_stats table | ✓ | ✓ |
| confidence_calibration_buckets table | ✓ | ✓ |
| confidence_calibration_summary table | ✓ | ✓ |

---

## 5. COMPONENTS TO RENAME

*(Logic is correct; only names carry trading identity)*

| Current Name | Renamed To | Type |
|---|---|---|
| StrategyEngine | RecommendationEngine | Service class |
| run_strategy_engine_loop | run_recommendation_engine_loop | Worker function |
| RiskEngine | QualityGate | Service class |
| run_risk_engine_loop | run_quality_gate_loop | Worker function |
| ExecutionEngine | PredictionCommitEngine | Service class |
| run_execution_engine_loop | run_prediction_commit_loop | Worker function |
| PositionTrackingService | PredictionTrackingService | Service class |
| run_position_tracking_loop | run_prediction_tracking_loop | Worker function |
| ExitEngine (partially) | PredictionExpiryMonitor | Service class |
| run_exit_engine_loop | run_prediction_expiry_loop | Worker function |
| PortfolioService | AnalyticsService | Service class |
| PortfolioAllocationService | PredictionAllocationService | Service class |
| PerformanceAnalyticsService | AccuracyAnalyticsService | Service class |
| CapitalManagementService | RecommendationBudgetService | Service class |
| PositionSizingService | AllocationWeightService | Service class |
| TradeEvaluationService | PredictionEvaluationService | Service class |
| TradeReplayService | PredictionReplayService | Service class |
| TradeDecision / trade_decisions | Recommendation / recommendations | Model + table |
| Order / orders | PredictionCommit / prediction_commits | Model + table |
| Position / positions | ActivePrediction / active_predictions | Model + table |
| risk_events | quality_gate_events | Table |
| trade_evaluations | prediction_evaluations | Table |
| position_repository.py | prediction_repository.py | Repository file |
| order_repository.py | commit_repository.py | Repository file |
| risk_repository.py | quality_gate_repository.py | Repository file |
| portfolio_repository.py | analytics_repository.py | Repository file |
| `side` column (LONG_YES/LONG_NO) | `direction` column (YES/NO) | DB column + enum |
| `entry_price` | `commit_probability` | DB column |
| `current_price` | `current_probability` | DB column |
| `fill_price` | `commit_probability` | DB column |
| `realized_pnl` | `resolution_delta` | DB column |
| `unrealized_pnl` | `probability_drift` | DB column |
| `peak_pnl_usdc` | `peak_drift` | DB column |
| `position_size_usdc` | `allocation_weight` | DB column |
| `status` OPEN / CLOSED | ACTIVE / RESOLVED | DB enum |
| `status` RISK_APPROVED / BLOCKED / FILLED | APPROVED / REJECTED / COMMITTED | DB enum |
| `win_rate` | `prediction_accuracy` | API field |
| `drawdown_percent` | `accuracy_degradation` | API field |
| `/api/v1/strategies/*` | `/api/v1/recommendations/*` | API paths |
| `/api/v1/orders/*` | `/api/v1/commits/*` | API paths |
| `/api/v1/positions/*` | `/api/v1/predictions/*` | API paths |
| `/api/v1/risk/*` | `/api/v1/quality-gate/*` | API paths |
| `/api/v1/portfolio/*` | `/api/v1/analytics/*` (merge) | API paths |
| `/api/v1/trades/*` | `/api/v1/records/*` | API paths |
| UI: "Execution Pipeline" panel | "Analysis Pipeline" | UI label |
| UI pipeline node "Strategy" | "RECOMMEND" | UI label |
| UI pipeline node "Risk" | "GATE" | UI label |
| UI pipeline node "Execution" | "COMMIT" | UI label |
| UI: "PAPER MODE" badge | Remove or "ANALYSIS MODE" | UI badge |
| UI: "Exposure" | "Coverage" | UI label |
| UI: `analyticsData.win_rate` | `analyticsData.prediction_accuracy` | JS variable |
| `ENGINE_NAMES_SHORT.execution_engine` | `"Prediction Commit"` | JS constant |
| `ENGINE_NAMES_SHORT.strategy_engine` | `"Recommendation Engine"` | JS constant |
| `BADGE_COLS.EXEC / EXECUTED` | `BADGE_COLS.COMMIT / COMMITTED` | JS constant |
| `BADGE_COLS.STRAT` | `BADGE_COLS.RECOMMEND` | JS constant |

---

## 6. COMPONENTS TO REMOVE

*(No probability equivalent — delete entirely)*

| Component | File / Location | Reason |
|---|---|---|
| `_compute_fee()` function | services/execution_engine.py | Fee is a trading concept; returns 0.0 by default; meaningless in probability context |
| `entry_fee_usdc` column | models/order.py → prediction_commits table | No transaction costs in probability analysis |
| `exit_fee_usdc` column | models/order.py → prediction_commits table | Same as above |
| `total_fee_usdc` aggregation | portfolio/analytics services | Derived from fee columns being removed |
| `EXIT_STOP_LOSS` trigger | services/exit_engine.py `_evaluate_triggers()` | Predictions resolve at 0/1, not at price thresholds |
| `EXIT_PROFIT_TARGET` trigger | services/exit_engine.py `_evaluate_triggers()` | Same |
| `peak_pnl_usdc` trailing reference in TRAILING_STOP | services/position_service.py, exit_engine.py | Dollar-based trailing; redesigned as CONFIDENCE_DETERIORATION |
| `DAILY_LOSS` risk rule | services/risk_engine.py | Dollar-loss limit; no capital to lose |
| `WEEKLY_LOSS` risk rule | services/risk_engine.py | Same |
| `EXECUTION_PAPER_MODE` config flag | config/settings.py | Concept does not apply — always analysis mode |
| `PAPER MODE` UI badge | index.html | Remove or replace with "ANALYSIS MODE" |
| `DAILY_TRADES` risk rule | services/risk_engine.py | Trading frequency limit; irrelevant |

---

## 7. MIGRATION ORDER

The migration must be performed in dependency order to avoid breaking the live system at any intermediate step.

### Phase A — No-risk groundwork (no DB changes)
1. Rename all Python service class names (internal only, no public API changes yet)
2. Rename all worker loop function names in `engine_workers.py`
3. Rename all repository class names and file names
4. Update all imports to reference new names
5. Remove `_compute_fee()`, fee columns from model (but keep in DB temporarily)
6. Remove `EXIT_STOP_LOSS` and `EXIT_PROFIT_TARGET` trigger branches from `ExitEngine`
7. Remove `DAILY_LOSS`, `WEEKLY_LOSS`, `DAILY_TRADES` rules from `RiskEngine.evaluate()`
8. Remove `EXECUTION_PAPER_MODE` config flag

### Phase B — Outcome Learning redesign (critical path)
9. Redesign `OutcomeLearningService` to fetch binary resolution from Gamma API directly
10. Remove dependency on `positions.realized_pnl` for `correct` determination
11. `outcome_learnings.position_id` becomes optional (NULL when no position)
12. Verify calibration still receives non-null `correct` rows on next cycle

### Phase C — DB column and enum renames (requires migration)
13. Rename `side` enum values: `LONG_YES → YES`, `LONG_NO → NO`
14. Rename `status` enums: `OPEN → ACTIVE`, `CLOSED → RESOLVED`, `RISK_APPROVED → APPROVED`, `BLOCKED → REJECTED`, `FILLED → COMMITTED`
15. Rename columns: `entry_price → commit_probability`, `current_price → current_probability`, `fill_price → commit_probability`, `realized_pnl → resolution_delta`, `unrealized_pnl → probability_drift`, `peak_pnl_usdc → peak_drift`, `position_size_usdc → allocation_weight`
16. Drop `entry_fee_usdc`, `exit_fee_usdc` columns
17. Rename tables: `trade_decisions → recommendations`, `orders → prediction_commits`, `positions → active_predictions`, `risk_events → quality_gate_events`, `trade_evaluations → prediction_evaluations`

### Phase D — API path renames (requires frontend update)
18. Rename API routes: `/strategies/* → /recommendations/*`, `/orders/* → /commits/*`, `/positions/* → /predictions/*`, `/risk/* → /quality-gate/*`, `/trades/* → /records/*`
19. Update frontend `fetch()` calls: `/positions/open → /predictions/active`, `/portfolio/* → /analytics/*` (merge)
20. Update `analyticsData` field names in `index.html` JS

### Phase E — UI label updates
21. Update `ENGINE_NAMES_SHORT` map in `index.html`
22. Update `BADGE_COLS` map
23. Rename pipeline nodes: Strategy → RECOMMEND, Risk → GATE, Execution → COMMIT
24. Update panel label "Execution Pipeline" → "Analysis Pipeline"
25. Remove "PAPER MODE" badge or replace with "ANALYSIS MODE"
26. Update AI Activity feed seed messages to use probability vocabulary

### Phase F — ExitEngine redesign
27. Redesign `TRAILING_STOP` trigger as `CONFIDENCE_DETERIORATION` (adverse probability drift threshold)
28. Redesign `SIGNAL_INVALIDATION` trigger as sustained confidence drop across all engines
29. Verify `EXPIRY_EXIT` trigger still fires correctly at `market_universe.end_time`

### Phase G — Portfolio/Analytics redesign
30. Redesign `PortfolioService` (→ AnalyticsService) metrics: replace P&L/ROI with accuracy rate, Brier score, calibration metrics
31. Redesign `CapitalManagementService` (→ RecommendationBudgetService) rules: replace dollar-loss limits with prediction-count limits
32. Update frontend Portfolio panel labels: "Capital" → "Budget", "Exposure" → "Coverage", "Total Return" → "Accuracy Trend"

---

## 8. RISK ASSESSMENT

| Risk | Severity | Mitigation |
|---|---|---|
| DB migration loses data | HIGH | All renames are non-destructive column/table renames; no rows deleted; roll back possible via ALTER TABLE |
| OutcomeLearning redesign breaks feedback loop | HIGH | Implement Phase B in a feature branch; verify non-null `correct` rows appear before merging |
| API path renames break frontend | MEDIUM | Update frontend fetch() calls in same PR as API renames (Phase D); test all 12 endpoints |
| ExitEngine redesign creates position leaks | MEDIUM | EXPIRY_EXIT trigger unchanged; positions always resolve at market expiry |
| Enum renames break existing DB rows | MEDIUM | Run UPDATE queries to migrate existing enum values before renaming enum types |
| Calibration stall during Phase B transition | LOW | OutcomeLearning continues writing NULL rows during transition; calibration skips them gracefully |

---

## 9. EXPECTED IMPACT

### Intelligence core
- **Preserved 100%** — all 9 scoring engines, consensus voting, calibration, dynamic weights, engine performance tracking survive intact
- **Improved** — Outcome Learning decoupled from execution pipeline; feedback loop becomes more reliable and faster

### Dashboard
- **Unchanged functionally** — same 12 fetch() calls, same data, same panels
- **Improved presentation** — probability-accurate vocabulary throughout; no trading terms visible to users

### API surface
- **Expanded clarity** — 55+ endpoints get probability-accurate paths; external consumers see a probability analysis API, not a trading bot API

### Codebase
- **Reduced complexity** — 4 functions removed, 12 config flags removed, 2 trigger branches deleted
- **Consistent vocabulary** — single semantic domain (probability analysis) throughout all 16 layers

### System identity
- **Transformed** — LIMWANPO AI presents unambiguously as a Professional Polymarket Probability Analysis Platform at every layer: code, DB schema, API, and UI

---

*This document is the definitive architectural decision for LIMWANPO AI Phase 2.*  
*No code was modified in producing this document.*

---

**AUDIT COMPLETE**  
**READY FOR PHASE 3**
