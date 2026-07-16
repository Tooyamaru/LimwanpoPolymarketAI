# LIMWANPO AI — PHASE 3 DECISION AUDIT
**Date:** 2026-07-07  
**Scope:** Full architectural audit — Trading Platform vs. Probability Analysis Platform  
**Method:** Static code analysis via parallel codebase explorers. No code was modified.  
**All citations verified against exact file names, class names, and column names.**

---

## TASK 1: END-TO-END EXECUTION TRACE

Each stage is traced in sequence with its input, output, object type, and downstream dependency.

---

### Stage 1 — Market Discovery

| Property | Detail |
|---|---|
| **Service** | `MarketUniverseService` (`services/market_universe_service.py`) |
| **Worker** | `run_universe_sync_loop` in `workers/engine_workers.py` — every 60 s |
| **Input** | Polymarket Gamma API: `GET /events`, `GET /series` via `gamma_series_client.py` |
| **Output** | Upserts rows into `market_universe` table: `condition_id`, `asset`, `is_active`, `status`, `end_time`, `question`, `series_slug`, `timeframe` |
| **Object type** | **Prediction object** — a reference catalogue of live binary markets, not a trade |
| **Required by** | Every downstream engine reads `market_universe` to resolve active conditions |
| **Trading?** | NO |
| **Probability?** | YES — defines the universe of prediction markets to analyse |

---

### Stage 2 — Market Price

| Property | Detail |
|---|---|
| **Service** | `MarketPriceService` (`services/market_price_service.py`) |
| **Worker** | `run_price_refresh_loop` in `workers/engine_workers.py` — every 10 s |
| **Input** | Polymarket CLOB `GET /book` via `clob_client.py` |
| **Output** | Upserts `market_price_snapshots` rows: `yes_mid`, `yes_bid`, `yes_ask`, `spread` |
| **CLOB interaction** | Read-only. `clob_client.py` issues `GET` requests only — zero `POST`, `PUT`, or `DELETE` calls found anywhere in the file |
| **Object type** | **Prediction object** — CLOB bid/ask represents the market-implied YES probability |
| **Required by** | `SignalEngine`, `OpportunityEngine`, `ExecutionEngine` (for simulated fill prices) |
| **Trading?** | NO (data fetch only) |
| **Probability?** | YES — CLOB bid/ask is the raw probability input |

---

### Stage 3 — Signal Generation

| Property | Detail |
|---|---|
| **Service** | `SignalEngine` (`services/signal_engine.py`) |
| **Worker** | `run_signal_engine_loop` — every 10 s |
| **Input** | `market_price_snapshots` (current vs. previous `yes_mid`, spread, seed) |
| **Output** | Creates `Signal` rows: `yes_mid_before`, `yes_mid_after`, `yes_mid_delta`, `spread_delta`, `seed_deviation`, `severity`, `confidence_score`, `regime`, `mtf_confirmed` |
| **Supporting logic** | `signal_confidence.py` — `compute_confidence()`, `detect_regime()` (RANGING / TRENDING_UP / TRENDING_DOWN / VOLATILE) |
| **Object type** | **Pure prediction object** — a scored probability-movement event, not a trade instruction |
| **Required by** | `StrategyEngine` (signal confidence gate), `DecisionEngine` (voting input), `OutcomeLearningService` |
| **Trading?** | NO |
| **Probability?** | YES — entirely |

---

### Stage 4 — Opportunity Scoring

| Property | Detail |
|---|---|
| **Service** | `OpportunityEngine` (`services/opportunity_engine.py`) |
| **Worker** | `run_opportunity_engine_loop` — every 30 s |
| **Input** | Scores from `MomentumEngine`, `TrendEngine`, `VolatilityEngine`, `SignalEngine`; `market_universe` |
| **Output** | Upserts `opportunities` rows: composite score 0–100, `direction`, `priority_score` (8-factor blend) |
| **Supporting engines** | `momentum_engine.py` (`run_momentum_engine_loop`), `trend_engine.py` (`run_trend_engine_loop`), `volatility_engine.py` (`run_volatility_engine_loop`) — each every 60 s, consuming Binance klines via `binance_market_data.py` |
| **Other scoring engines** | `orderbook_engine.py` (`OrderbookEngine`), `funding_engine.py` (`FundingEngine`), `news_engine.py` (`NewsEngine`), `market_context_engine.py` (`MarketContextEngine`), `polymarket_market_engine.py` (`PolymarketMarketEngine` — market quality/behaviour) |
| **Object type** | **Pure prediction object** — ranked market attractiveness, not a trade |
| **Required by** | `StrategyEngine`, `DecisionEngine`, `PositionService` (current price lookup via `yes_mid`) |
| **Trading?** | NO |
| **Probability?** | YES — entirely |

---

### Stage 5 — Decision

This stage has **two independent sub-engines** with different roles.

#### 5a — DecisionEngine (Probability Verdict)

| Property | Detail |
|---|---|
| **Service** | `DecisionEngine` (`services/decision_engine.py`) |
| **Worker** | `run_decision_engine_loop` — every 60 s |
| **Main method** | `decide()` — calls `_decide_market()` per active condition |
| **Consensus logic** | `_compute_consensus()` — embedded method; no standalone `consensus_engine.py` exists |
| **Input** | All score tables: `funding_scores`, `market_context_scores`, `market_quality_scores`, `momentum_scores`, `news_scores`, `opportunities`, `orderbook_scores`, `trend_scores`, `volatility_scores`; `engine_weights` (from `DynamicWeightService`) |
| **Output** | Appends `decision_logs` row: `decision` (BUY_YES / BUY_NO / WAIT), `confidence`, `vote_score`, `consensus_score`, `agreement_level`, `conflict_detected`, `entry_quality_score`, per-engine score columns, `supporting_engines`, `reasons` |
| **Object type** | **Pure prediction object** — a structured probability verdict, append-only log |
| **Required by** | `OutcomeLearningService` (reads via `decision_log_id`), `EnginePerformanceService`, `DynamicWeightService`, Dashboard |
| **Trading?** | NO — does not create orders or trade decisions |
| **Probability?** | YES — entirely |

#### 5b — StrategyEngine (Trade Intent)

| Property | Detail |
|---|---|
| **Service** | `StrategyEngine` (`services/strategy_engine.py`) |
| **Worker** | `run_strategy_engine_loop` — every 60 s |
| **Input** | `opportunities` rows; `Signal` confidence scores; `PositionSizingService` for USDC amount |
| **Output** | Creates `trade_decisions` rows with status `PENDING` / `WATCH` / `SKIP`; sets `position_size_usdc`, `direction`, `yes_mid`, `yes_bid`, `yes_ask`, `opportunity_score` |
| **Object type** | **Hybrid** — a trade intent record; becomes the paper-trade seed if approved by `RiskEngine` |
| **Required by** | `RiskEngine` (consumes PENDING rows), `ExitEngine` (generates CLOSE_POSITION rows), Dashboard |
| **Trading?** | YES (in paper mode) |
| **Probability?** | YES — direction and sizing are fully derived from probability scores |

---

### Stage 6 — Risk

| Property | Detail |
|---|---|
| **Service** | `RiskEngine` (`services/risk_engine.py`) |
| **Worker** | `run_risk_engine_loop` — every 15 s |
| **Main method** | `evaluate()` (not `run()`) |
| **Input** | `trade_decisions` rows with status `PENDING`; pre-fetched `open_positions` from `positions` table; `daily_trades` count from `orders` table; `daily_loss` (unrealized PnL) from `positions` table |
| **Output** | Mutates `trade_decisions.status` → `RISK_APPROVED` or `BLOCKED`; creates `risk_events` rows via `risk_repository.py` |
| **Rules evaluated** | DUPLICATE_POSITION, MAX_OPEN_POSITIONS, MAX_EXPOSURE, DAILY_LOSS, DAILY_TRADES, PORTFOLIO_EXPOSURE_LIMIT, PORTFOLIO_POSITION_LIMIT, ASSET_EXPOSURE_LIMIT, TIMEFRAME_POSITION_LIMIT; capital rules (DAILY_LOSS_LIMIT, WEEKLY_LOSS_LIMIT, LOSS_STREAK_LIMIT, MAX_DRAWDOWN_LIMIT) via `CapitalManagementService` (`capital_management_service.py`) |
| **Exit handling** | `CLOSE_POSITION` decisions are auto-approved — no rules applied |
| **Object type** | **Hybrid** — a paper-trade gate; structurally identical to production risk rules but applied entirely to simulated state |
| **Required by** | `ExecutionEngine` (only consumes `RISK_APPROVED` decisions) |
| **Trading?** | YES (gates paper trades) |
| **Probability?** | Partial — `CapitalManagementService` draws on P&L metrics derived from the paper simulation |

---

### Stage 7 — Execution

| Property | Detail |
|---|---|
| **Service** | `ExecutionEngine` (`services/execution_engine.py`) — self-describes as "Layer 7 (Paper Mode)" |
| **Worker** | `run_execution_engine_loop` — every 30 s |
| **Main method** | `run()` |
| **Input** | `trade_decisions` rows with status `RISK_APPROVED` |
| **Output** | Creates `orders` rows with computed `fill_price` and status `FILLED`; calls module-level `_compute_fee()` |
| **Fill price logic** | Entry: `yes_ask` (LONG_YES) or `1 - yes_bid` (LONG_NO) from internal snapshots — no external API call |
| **Exchange interaction** | **NONE.** `clob_client.py` has zero POST/PUT/DELETE methods. No wallet calls. No on-chain settlement anywhere in the codebase. |
| **Fee logic** | `_compute_fee()` applies `POLYMARKET_FEE_RATE`; returns 0.0 by default in paper mode |
| **Object type** | **Paper simulation only** — `orders` rows are local DB records with no external counterpart |
| **Required by** | `PositionTrackingService` (creates `positions` from `FILLED` orders) |
| **Trading?** | Structurally YES, operationally NO — pure simulation |
| **Probability?** | NO |

---

### Stage 8 — Position

| Property | Detail |
|---|---|
| **Service** | `PositionTrackingService` (`services/position_service.py`) |
| **Worker** | `run_position_tracking_loop` — every 30 s |
| **Input** | `orders` rows with status `FILLED`; `opportunities` rows for current `yes_mid` |
| **Output** | Creates `positions` rows; updates `current_price`, `unrealized_pnl`, `peak_pnl_usdc`; on close: sets `realized_pnl`, `status = CLOSED` |
| **Key methods** | `create_position_from_fill()`, `update_market_prices()`, `recalculate_pnl()`, `close_position()` |
| **`close_position()`** | Finalises `realized_pnl`, deducts fees, marks `CLOSED` — all local DB writes, no API calls |
| **Object type** | **Paper simulation only** — no capital moves |
| **Required by** | `ExitEngine`, `RiskEngine` (PnL inputs), `PortfolioService`, `TradeEvaluationService`, `OutcomeLearningService` (reads `position_id` and `realized_pnl` for correctness determination) |
| **Trading?** | Structurally YES, operationally NO |
| **Probability?** | NO |

---

### Stage 9 — Portfolio

| Property | Detail |
|---|---|
| **Services** | `PortfolioService` (`services/portfolio_service.py`), `PortfolioAllocationService` (`services/portfolio_allocation_service.py`), `PerformanceAnalyticsService` (`services/performance_analytics_service.py`) |
| **Repositories** | `portfolio_repository.py` |
| **Input** | Aggregates `positions`, `orders`, `trade_decisions` table data |
| **Output** | Read-only metrics: total capital, unrealized/realized P&L, ROI, allocation breakdowns by asset and timeframe |
| **Capital tracked** | Paper capital only — no USDC wallet, no on-chain balance |
| **Object type** | **Paper simulation only** |
| **Required by** | Dashboard; `RiskEngine` (via `CapitalManagementService` for drawdown checks) |
| **Trading?** | Structurally YES, operationally NO |
| **Probability?** | NO |

---

### Stage 10 — Outcome Learning

| Property | Detail |
|---|---|
| **Service** | `OutcomeLearningService` (`services/outcome_learning_service.py`) |
| **Worker** | `run_outcome_learning_loop` — every 300 s |
| **Input** | `market_universe` (expired conditions where `end_time < now`, `status == "active"`); most recent `decision_logs` row per `condition_id`; most recent CLOSED `positions` row per `condition_id` |
| **Output** | Creates `outcome_learnings` rows with fields: `decision_log_id`, `position_id`, `condition_id`, `prediction`, `correct`, `actual_pnl`, `confidence`, `consensus_score`, etc. |
| **Correctness logic** | If a CLOSED position exists: `correct = True` if `realized_pnl > 0`, else `False`. If no CLOSED position exists: `correct = None`, `outcome_type = NO_POSITION`. Records with `correct = None` are **skipped by all downstream calibration logic**. |
| **Dependency on execution** | **CRITICAL:** Without closed `positions` rows, `outcome_learnings.correct` is always `NULL`. Calibration and weight optimisation consume only non-null `correct` rows, so disabling the execution pipeline silences the entire feedback loop. |
| **Foreign key links** | `outcome_learnings.decision_log_id` → `decision_logs.id`; `outcome_learnings.position_id` → `positions.id` |
| **Object type** | **Hybrid** — pure probability intent (did the AI predict correctly?) but structurally anchored to closed positions for the correctness signal |
| **Required by** | `ConfidenceCalibrationService`, `DynamicWeightService`, `EnginePerformanceService` |
| **Trading?** | Partial — requires a closed paper position to produce usable `correct` rows |
| **Probability?** | YES — the purpose is probabilistic validation |

---

### Stage 11 — Calibration

| Property | Detail |
|---|---|
| **Service** | `ConfidenceCalibrationService` (`services/confidence_calibration_service.py`) |
| **Repository** | `confidence_calibration_repository.py` |
| **Main method** | `recompute(session)` |
| **Input** | `outcome_learnings` rows where both `confidence` and `correct` are NOT NULL |
| **Output** | Upserts `confidence_calibration_buckets` (5%-wide buckets e.g. 50–55%, 55–60%) and `confidence_calibration_summary` (ACE, ECE metrics) via `cal_repo.upsert_bucket()`, `cal_repo.upsert_summary()` |
| **Object type** | **Pure prediction object** |
| **Required by** | `DynamicWeightService`, Dashboard health display |
| **Dependency on execution** | If `outcome_learnings.correct` is always NULL (no closed positions), `recompute()` has no valid input rows and produces no calibration data |
| **Trading?** | NO |
| **Probability?** | YES — entirely |

---

### Stage 12 — Engine Performance & Weight Optimisation

| Property | Detail |
|---|---|
| **Services** | `EnginePerformanceService` (`services/engine_performance_service.py`), `DynamicWeightService` (`services/dynamic_weight_service.py`), `EngineScorecardService` (`services/engine_scorecard_service.py`) |
| **Worker** | `run_dynamic_weight_loop` — every 1800 s |
| **Input** | `outcome_learnings` (per-engine accuracy); `engine_performance_stats` |
| **Output** | Updates `engine_weights` table: `current_weight`, `performance_factor` per engine name |
| **Object type** | **Pure prediction object** — self-optimising probability weighting |
| **Required by** | `DecisionEngine._load_effective_weights()` reads `engine_weights` at each `decide()` call |
| **Dependency on execution** | Same as Calibration: if no closed positions produce non-null `correct` rows, weight updates stall |
| **Trading?** | NO |
| **Probability?** | YES — entirely |

---

## TASK 2: TRADING BEHAVIOR DETECTION

For each trading behavior, exact file, function, and classification:

| Behavior | File | Function / Method | Classification |
|---|---|---|---|
| **Opening positions** | `services/execution_engine.py` | `_execute_decision()` | **B — Paper simulation only.** Fills from internal `yes_ask`/`yes_bid` snapshots; no external API POST. |
| **Closing positions** | `services/execution_engine.py` | `_execute_close_decision()` | **B — Paper simulation only.** Exit price from internal bid data; no CLOB cancel or settlement. |
| | `services/position_service.py` | `close_position()` | **B — Paper simulation only.** Writes `realized_pnl` to `positions` table; no on-chain event. |
| **Order lifecycle** | `services/execution_engine.py` | `run()` | **B — Paper simulation only.** Polls `RISK_APPROVED` `trade_decisions`; creates `orders` rows. |
| | `repositories/order_repository.py` | `create_order()` | **B — Paper simulation only.** Inserts simulated fill into local DB. |
| **Capital allocation** | `services/position_sizing_service.py` | (computes `position_size_usdc`) | **B — Paper simulation only.** Allocates from a virtual capital pool; no wallet interaction. |
| **Exposure management** | `services/risk_engine.py` | `evaluate()` — `MAX_EXPOSURE`, `PORTFOLIO_EXPOSURE_LIMIT`, `ASSET_EXPOSURE_LIMIT` checks | **B — Paper simulation only.** Rules applied to simulated `positions`, not real USDC. |
| **Profit calculation** | `services/position_service.py` | `recalculate_pnl()` | **B — Paper simulation only.** `unrealized_pnl = (current_price − entry_price) × size`. |
| **Loss calculation** | `services/position_service.py` | `recalculate_pnl()` | **B — Paper simulation only.** Same function; negative delta produces loss figure. |
| **Drawdown** | `services/capital_management_service.py` | `evaluate()` — `MAX_DRAWDOWN_LIMIT` rule | **B — Paper simulation only.** Drawdown computed from simulated `positions` PnL, not real capital. |
| **Fee calculation** | `services/execution_engine.py` | `_compute_fee()` (module-level function) | **B — Paper simulation only.** Applies `POLYMARKET_FEE_RATE`; returns 0.0 by default. |
| **Trade settlement** | — | — | **D — Never executed.** No settlement logic exists anywhere in the codebase. No on-chain finality check. |
| **Portfolio balancing** | `services/portfolio_service.py`, `services/portfolio_allocation_service.py` | (allocation/summary endpoints) | **B — Paper simulation only.** Read-only aggregation of simulated positions; no rebalancing actions. |
| **Position sizing** | `services/position_sizing_service.py` | (size computation) | **B — Paper simulation only.** Feeds `trade_decisions.position_size_usdc`; no capital movement. |
| **Risk blocking** | `services/risk_engine.py` | `evaluate()` → status → `BLOCKED` | **B — Paper simulation only.** Blocks paper trades, not real orders. |
| **Stop loss** | `services/exit_engine.py` | `_evaluate_triggers()` — `STOP_LOSS` branch | **B — Paper simulation only.** Generates `CLOSE_POSITION` `trade_decision`; no CLOB cancel call. |
| **Take profit** | `services/exit_engine.py` | `_evaluate_triggers()` — `PROFIT_TARGET` branch | **B — Paper simulation only.** |
| **Trailing stop** | `services/exit_engine.py` | `_evaluate_triggers()` — `TRAILING_STOP` branch: `exit_pnl < (peak_pnl_usdc − trailing_drawdown_threshold)` | **B — Paper simulation only.** |
| **Execution retry** | — | — | **D — Never executed.** No retry logic found in `execution_engine.py`. |
| **Exchange interaction** | `services/clob_client.py` | `get_market()`, `_fetch_order_book()` | **A — Active production logic.** But read-only `GET` calls only. Zero `POST`/`PUT`/`DELETE` methods exist in the file. |
| **Broker interaction** | — | — | **D — Never executed.** No broker API integration exists. |
| **Wallet interaction** | — | — | **D — Never executed.** No wallet SDK, no private key usage, no USDC transfer logic found anywhere in the codebase. |

**Critical finding:** The Polymarket CLOB client (`clob_client.py`) is entirely read-only. The architecture has worker loops and data structures that mirror a real trading platform, but the exchange boundary — the point at which a `POST /order` would be submitted — does not exist. The system has **no order submission capability** in its current form.

---

## TASK 3: PROBABILITY BEHAVIOR DETECTION

### Engines forming the TRUE intelligence core

| Engine / Service | File | What it computes | Probability? |
|---|---|---|---|
| `SignalEngine` | `signal_engine.py` | Detects `MID_MOVE`, `SEED_DEVIATION`, `SPREAD_CHANGE`; scores confidence and regime | YES |
| `signal_confidence.py` | `signal_confidence.py` | `compute_confidence()`, `detect_regime()` — RANGING/TRENDING/VOLATILE | YES |
| `MomentumEngine` | `momentum_engine.py` | Binance kline momentum score + direction + confidence | YES |
| `TrendEngine` | `trend_engine.py` | Binance kline trend direction + confidence | YES |
| `VolatilityEngine` | `volatility_engine.py` | Binance volatility regime scoring | YES |
| `OrderbookEngine` | `orderbook_engine.py` | Bid/ask volume imbalance → direction confidence | YES |
| `FundingEngine` | `funding_engine.py` | Funding rate → probability prediction | YES |
| `NewsEngine` | `news_engine.py` | Sentiment → impact confidence | YES |
| `PolymarketMarketEngine` | `polymarket_market_engine.py` | Market quality scoring and behaviour classification (Excellent/Healthy/Good/Illiquid/Avoid/High Risk) | YES |
| `MarketContextEngine` | `market_context_engine.py` | Phase/timing confidence | YES |
| `MarketReferenceService` | `market_reference_service.py` | `fetch_opening_price()` from Binance klines — "Price to Beat" probability anchor | YES |
| `OpportunityEngine` | `opportunity_engine.py` | Composite 0–100 score; 8-factor `priority_score` blend | YES |
| `DecisionEngine` | `decision_engine.py` | `decide()` → `_decide_market()` → `_compute_consensus()` → BUY_YES / BUY_NO / WAIT verdict with confidence and agreement metrics | YES |
| `OutcomeLearningService` | `outcome_learning_service.py` | Validates AI predictions against binary market resolutions (requires closed positions for non-null `correct`) | YES (with execution dependency) |
| `ConfidenceCalibrationService` | `confidence_calibration_service.py` | `recompute()` — ECE/ACE calibration across 5% confidence buckets | YES (with execution dependency) |
| `DynamicWeightService` | `dynamic_weight_service.py` | Recomputes per-engine `current_weight` from accuracy history | YES (with execution dependency) |
| `EnginePerformanceService` | `engine_performance_service.py` | Per-engine accuracy and `sample_count` | YES (with execution dependency) |
| `EngineScorecardService` | `engine_scorecard_service.py` | Scorecard aggregation across engines | YES |
| `MarketTypePerformanceService` | `market_type_performance_service.py` | Win-rate tracking by market type | YES (with execution dependency) |
| `TradeReplayService` | `trade_replay_service.py` | Post-hoc replay and analysis of completed positions | YES (with execution dependency) |

**Key finding:** 14 intelligence modules are fully independent of the execution pipeline (they run regardless of whether paper trading is enabled). 6 modules — `OutcomeLearningService`, `ConfidenceCalibrationService`, `DynamicWeightService`, `EnginePerformanceService`, `MarketTypePerformanceService`, `TradeReplayService` — **require closed `positions` rows to produce non-null `correct` values**. Without those rows, these services continue to run but produce no usable output (all `correct = NULL` rows are skipped by calibration).

---

## TASK 4: DEPENDENCY IMPACT

For every trading-related service, each downstream system is evaluated.

---

### StrategyEngine (`services/strategy_engine.py`)

**Purpose:** Converts `OpportunityEngine` output into `trade_decisions` rows (`PENDING`/`WATCH`/`SKIP`).

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | **FUNCTIONAL BREAK** — `outcome_learnings` links via `decision_log_id` to `decision_logs`, but the learning service also reads `positions` (which StrategyEngine indirectly seeds). Without PENDING decisions, no orders are created, no positions exist, no `correct` values are populated. Calibration, weights, and performance stall. |
| Calibration | **FUNCTIONAL BREAK** — depends on non-null `correct` from outcome learning |
| Dynamic Weight | **FUNCTIONAL BREAK** — depends on calibration output |
| Engine Performance | **FUNCTIONAL BREAK** — depends on outcome rows |
| Dashboard | `/strategies/active` endpoint returns empty |
| Health Monitor | `run_strategy_engine_loop` heartbeat disappears |
| Workers | Loop becomes orphaned |
| API | `/strategies/active` empty |
| Database | `trade_decisions` table goes empty |

**Verdict: CONVERT** — rename to `RecommendationEngine`; emit "Probability Recommendations" instead of "Trade Decisions". The record structure is compatible.

---

### RiskEngine (`services/risk_engine.py`) — main method: `evaluate()`

**Purpose:** Gates `trade_decisions` rows PENDING → RISK_APPROVED / BLOCKED.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | **FUNCTIONAL BREAK** — without RISK_APPROVED decisions, `ExecutionEngine` creates no orders, so positions never exist, so `correct` is always NULL |
| Calibration | **FUNCTIONAL BREAK** (cascades from above) |
| Dynamic Weight | **FUNCTIONAL BREAK** (cascades) |
| Engine Performance | **FUNCTIONAL BREAK** (cascades) |
| Dashboard | `/risk/blocked` endpoint returns empty |
| Health Monitor | `run_risk_engine_loop` heartbeat disappears |
| Workers | Loop becomes orphaned |
| API | `/risk/blocked` empty |
| Database | `risk_events` table goes empty |

**Verdict: CONVERT** — rename to `QualityGate`; reframe rules as prediction deduplication and coverage-balance controls (DUPLICATE_CONDITION → dedup, MAX_OPEN_POSITIONS → max active predictions).

---

### ExecutionEngine (`services/execution_engine.py`) — main method: `run()`

**Purpose:** Converts `RISK_APPROVED` `trade_decisions` into `orders` rows.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | **FUNCTIONAL BREAK** — no `orders` → no `positions` → no closed positions → `correct = NULL` for all outcome rows |
| Calibration | **FUNCTIONAL BREAK** (cascades) |
| Dynamic Weight | **FUNCTIONAL BREAK** (cascades) |
| Engine Performance | **FUNCTIONAL BREAK** (cascades) |
| Dashboard | `/orders/open` empty; `/positions/stats` empty |
| Health Monitor | Heartbeat disappears |
| Workers | Loop becomes orphaned |
| API | Multiple trading endpoints empty |
| Database | `orders` table empty |

**Verdict: CONVERT** — rename to `PredictionCommitEngine`; commit the probability recommendation as a timestamped record (without fill price semantics). The purpose — creating a concrete, timed record of the AI's active prediction — is valid in both contexts.

---

### PositionTrackingService (`services/position_service.py`)

**Purpose:** Creates `positions` from filled `orders`; updates PnL; manages lifecycle to CLOSED.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | **FUNCTIONAL BREAK** — `OutcomeLearningService` reads `positions` where `status = CLOSED` and `realized_pnl` to determine `correct`. Without closed positions, all outcome rows have `correct = NULL`. |
| Calibration | **FUNCTIONAL BREAK** (cascades) |
| Dynamic Weight | **FUNCTIONAL BREAK** (cascades) |
| Engine Performance | **FUNCTIONAL BREAK** (cascades) |
| Dashboard | `/positions/stats` empty |
| ExitEngine | Has nothing to evaluate; triggers never fire |
| RiskEngine | PnL inputs drop to zero; drawdown rules always pass |
| Portfolio | No position data to aggregate |

**Verdict: CONVERT** — rename to `PredictionTrackingService`; track the prediction's "probability drift" (current `yes_mid` vs. commit probability) over its lifetime in place of P&L.

---

### ExitEngine (`services/exit_engine.py`)

**Purpose:** Evaluates open positions for STOP_LOSS / PROFIT_TARGET / TRAILING_STOP / EXPIRY_EXIT / SIGNAL_INVALIDATION triggers.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | **FUNCTIONAL BREAK** — positions would never receive `status = CLOSED`; `realized_pnl` stays NULL; `correct` stays NULL |
| Position lifecycle | Predictions (positions) accumulate indefinitely with no resolution — a resource and logical leak |
| Dashboard | Exit data disappears |
| Health Monitor | Heartbeat disappears |

**Verdict: CONVERT** — rename to `PredictionExpiryMonitor`. The `EXPIRY_EXIT` trigger (closes position at market resolution) is already the correct behaviour for a probability platform. The `STOP_LOSS` and `PROFIT_TARGET` triggers require **behavioral redesign** (see Task 7). The `SIGNAL_INVALIDATION` trigger should be redesigned as a confidence-degradation detector.

---

### PortfolioService / PortfolioAllocationService / PerformanceAnalyticsService

**Files:** `services/portfolio_service.py`, `services/portfolio_allocation_service.py`, `services/performance_analytics_service.py`  
**Repository:** `repositories/portfolio_repository.py`

**Purpose:** Aggregates paper P&L, capital allocation, ROI metrics.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | Unaffected (different data path) |
| Calibration | Unaffected |
| Dynamic Weight | Unaffected |
| Engine Performance | Unaffected |
| RiskEngine | `CapitalManagementService` loses portfolio P&L input; drawdown checks degrade |
| Dashboard | Portfolio section goes blank |
| API | `/analytics/performance`, `/portfolio/*` endpoints empty |

**Verdict: CONVERT** — rename collectively to `AnalyticsService`; replace P&L metrics with accuracy rate, Brier score, confidence-weighted hit rate, and recommendation coverage.

---

### CapitalManagementService (`services/capital_management_service.py`)

**Purpose:** Evaluates DAILY_LOSS_LIMIT, WEEKLY_LOSS_LIMIT, LOSS_STREAK_LIMIT, MAX_DRAWDOWN_LIMIT rules; called by `RiskEngine.evaluate()`.

| Downstream | Impact if removed |
|---|---|
| RiskEngine | Loses 4 of its ~10 rules; simpler but functional |
| All others | Unaffected |

**Verdict: CONVERT** — reframe as `RecommendationBudgetService`; rules become coverage-balance controls (max active predictions per period, concentration limits) rather than loss-based limits.

---

### PositionSizingService (`services/position_sizing_service.py`)

**Purpose:** Computes `position_size_usdc` fed into `trade_decisions` by `StrategyEngine`.

| Downstream | Impact if removed |
|---|---|
| StrategyEngine | `position_size_usdc` column goes NULL/zero |
| RiskEngine | `PORTFOLIO_EXPOSURE_LIMIT` check loses input |
| All others | Unaffected |

**Verdict: CONVERT** — rename to `AllocationWeightService`; compute a confidence-proportional "allocation weight" (0.0–1.0) rather than a USDC amount.

---

### TradeEvaluationService (`services/trade_evaluation_service.py`)

**Purpose:** Post-trade quality analysis producing `trade_evaluations` rows with `entry_quality`, `exit_quality`, `timing_score`, `pnl_efficiency`.

| Downstream | Impact if removed |
|---|---|
| Outcome Learning | Unaffected (separate data path) |
| Dashboard | `/trade-evaluations` endpoint empty |
| All learning services | Unaffected |

**Verdict: CONVERT** — rename to `PredictionEvaluationService`; replace `pnl_efficiency` / `realized_pnl` dependency with probability-drift efficiency (how close was the prediction to the actual resolution probability at commit time).

---

### TradeReplayService (`services/trade_replay_service.py`)

**Purpose:** Post-hoc replay and analysis of completed position histories.

**Verdict: CONVERT** — rename to `PredictionReplayService`; replay prediction confidence evolution rather than P&L trajectory.

---

## TASK 5: DATABASE IMPACT

| Table | Classification | Reason |
|---|---|---|
| `market_universe` | **Pure Probability** | Reference catalogue of Polymarket conditions — entirely analytical |
| `market_price_snapshots` | **Pure Probability** | CLOB bid/ask = YES/NO probability time-series |
| `signal_scores` | **Pure Probability** | Price-event detection and confidence scoring |
| `momentum_scores` | **Pure Probability** | Binance kline momentum analysis |
| `trend_scores` | **Pure Probability** | Binance kline trend analysis |
| `volatility_scores` | **Pure Probability** | Binance volatility regime |
| `orderbook_scores` | **Pure Probability** | Bid/ask volume imbalance |
| `funding_scores` | **Pure Probability** | Funding rate prediction |
| `news_scores` | **Pure Probability** | Sentiment scoring |
| `market_quality_scores` | **Pure Probability** | Market health/behaviour classification |
| `market_context_scores` | **Pure Probability** | Phase/timing confidence |
| `opportunities` | **Pure Probability** | Composite market attractiveness score |
| `decision_logs` | **Pure Probability** | Stores probability consensus verdict (BUY_YES/BUY_NO/WAIT) — append-only log; the `decision_log_id` anchor for outcome learning |
| `engine_performance_stats` | **Pure Probability** | Per-engine accuracy tracking |
| `engine_weights` | **Pure Probability** | Dynamic engine weight optimisation |
| `confidence_calibration_buckets` | **Pure Probability** | Calibration accuracy by confidence bucket |
| `confidence_calibration_summary` | **Pure Probability** | ECE/ACE aggregate metrics |
| `orders` | **Pure Trading** | Simulated fill records — only meaningful in trade context |
| `positions` | **Pure Trading** | Simulated position state and P&L — only meaningful in trade context; however currently serves as the **correctness anchor** for outcome learning |
| `risk_events` | **Pure Trading** | Paper-trade gate audit log |
| `trade_decisions` | **Hybrid** | Bridge between analysis and execution. Contains probability fields (`direction`, `confidence`, `opportunity_score`, `yes_mid`) and trading fields (`position_size_usdc`, `status = RISK_APPROVED`). Required by outcome learning indirectly (seeds the position chain). |
| `trade_evaluations` | **Hybrid** | Post-trade quality analysis. Uses `position_id` (trading anchor) but computes `entry_quality_score`, `timing_score`, `pnl_efficiency` (analytical metrics). Anchored to positions but purpose is probabilistic evaluation. |
| `outcome_learnings` | **Hybrid** | Pure probability intent (was the prediction correct?) but structurally requires `decision_log_id` (probability) AND `position_id` with `realized_pnl` (trading) to populate `correct`. Without closed positions, all rows have `correct = NULL`. |
| `market_type_performance` | **Hybrid** | `win_rate` / `total_trades` are trading vocabulary but the underlying concept (prediction accuracy by market type) is probabilistic. Currently feeds from closed-position outcomes. |

**Hybrid table detail:**  
The four hybrid tables form a single feedback chain: `trade_decisions` → `orders` → `positions` (CLOSED) → `outcome_learnings.correct` → `confidence_calibration_*` → `engine_weights`. The chain's **purpose** is probabilistic (did the AI predict correctly?) but its **correctness signal** is currently defined as `realized_pnl > 0` on a closed paper position. This is the single structural coupling point between the trading identity and the probability intelligence. Replacing `realized_pnl > 0` with `actual_resolution == predicted_direction` (from Polymarket's resolved market endpoint) would sever this coupling and allow the feedback loop to function without any position tracking.

---

## TASK 6: FINAL DECISION MATRIX

| Module | Current Purpose | Real Usage | Required? | Trading? | Probability? | Recommendation |
|---|---|---|---|---|---|---|
| `MarketUniverseService` | Syncs active Polymarket conditions | Active | YES | NO | YES | **KEEP** |
| `MarketPriceService` | Fetches CLOB bid/ask snapshots | Active | YES | NO | YES | **KEEP** |
| `clob_client.py` | Read-only CLOB data client | Active | YES | NO | YES | **KEEP** |
| `gamma_series_client.py` | Gamma API client for market discovery | Active | YES | NO | YES | **KEEP** |
| `binance_market_data.py` | Binance kline data for technical engines | Active | YES | NO | YES | **KEEP** |
| `SignalEngine` | Price-event detection + confidence | Active | YES | NO | YES | **KEEP** |
| `signal_confidence.py` | Regime detection + confidence scoring | Active | YES | NO | YES | **KEEP** |
| `MomentumEngine` | Binance kline momentum | Active | YES | NO | YES | **KEEP** |
| `TrendEngine` | Binance kline trend | Active | YES | NO | YES | **KEEP** |
| `VolatilityEngine` | Binance volatility regime | Active | YES | NO | YES | **KEEP** |
| `OrderbookEngine` | Bid/ask imbalance scoring | Active | YES | NO | YES | **KEEP** |
| `FundingEngine` | Funding rate prediction | Active | YES | NO | YES | **KEEP** |
| `NewsEngine` | Sentiment scoring | Active | YES | NO | YES | **KEEP** |
| `PolymarketMarketEngine` | Market quality + behaviour classification | Active | YES | NO | YES | **KEEP** |
| `MarketContextEngine` | Phase + timing confidence | Active | YES | NO | YES | **KEEP** |
| `MarketReferenceService` | Opening price anchor ("Price to Beat") | Active | YES | NO | YES | **KEEP** |
| `OpportunityEngine` | Composite 0–100 market score | Active | YES | NO | YES | **KEEP** |
| `DecisionEngine` (`decide()`) | Multi-engine consensus verdict | Active | YES | NO | YES | **KEEP** |
| `_compute_consensus()` | Embedded in `decision_engine.py` | Active | YES | NO | YES | **KEEP** |
| `OutcomeLearningService` | Prediction vs. reality validation | Active | YES | NO* | YES | **KEEP** (but correctness source needs redesign — see Task 7) |
| `ConfidenceCalibrationService` | ECE/ACE calibration metrics | Active | YES | NO | YES | **KEEP** |
| `DynamicWeightService` | Engine weight optimisation | Active | YES | NO | YES | **KEEP** |
| `EnginePerformanceService` | Per-engine accuracy tracking | Active | YES | NO | YES | **KEEP** |
| `EngineScorecardService` | Scorecard aggregation | Active | YES | NO | YES | **KEEP** |
| `StrategyEngine` | Converts opportunities to TradeDecisions | Active | YES | YES | YES | **CONVERT** → `RecommendationEngine`; emit "Probability Recommendations" |
| `RiskEngine` (`evaluate()`) | Gates TradeDecisions PENDING→APPROVED | Active | YES | YES | NO | **CONVERT** → `QualityGate`; reframe rules as deduplication + coverage limits |
| `ExecutionEngine` (`run()`) | Paper-mode order simulation | Active | YES | YES | NO | **CONVERT** → `PredictionCommitEngine`; commit timestamped recommendation records |
| `PositionTrackingService` | Tracks simulated positions + PnL | Active | YES | YES | NO | **CONVERT** → `PredictionTrackingService`; track probability drift over lifetime |
| `ExitEngine` | Stop/profit/expiry triggers | Active | YES | YES | NO | **CONVERT** → `PredictionExpiryMonitor`; EXPIRY_EXIT stays; STOP_LOSS/PROFIT_TARGET require redesign |
| `PortfolioService` | Aggregates paper P&L | Active | YES | YES | NO | **CONVERT** → `AnalyticsService`; report accuracy rate and calibration metrics |
| `PortfolioAllocationService` | Allocation breakdowns | Active | YES | YES | NO | **CONVERT** → prediction coverage breakdowns |
| `PerformanceAnalyticsService` | ROI and capital metrics | Active | YES | YES | NO | **CONVERT** → Brier score, hit rate, calibration curve |
| `CapitalManagementService` | Drawdown/loss-streak rules | Active | YES | YES | NO | **CONVERT** → `RecommendationBudgetService`; reframe as coverage balance rules |
| `PositionSizingService` | Computes `position_size_usdc` | Active | YES | YES | NO | **CONVERT** → `AllocationWeightService`; confidence-proportional weight |
| `TradeEvaluationService` | Post-trade quality analysis | Active | YES | YES | YES | **CONVERT** → `PredictionEvaluationService`; replace `pnl_efficiency` with probability-drift efficiency |
| `TradeReplayService` | Post-hoc position replay | Active | YES | YES | NO | **CONVERT** → `PredictionReplayService`; replay confidence evolution |
| `MarketTypePerformanceService` | Win-rate by market type | Active | YES | NO* | YES | **KEEP** (reframe `total_trades` → `total_predictions`) |
| `_compute_fee()` in `execution_engine.py` | Paper fee calculation | Active | NO | YES | NO | **REMOVE** — returns 0.0 by default; irrelevant in probability context |
| `orders` table | Simulated fill records | Active | YES* | YES | NO | **CONVERT** → `prediction_commits` — timestamp and commit probability only |
| `positions` table | Simulated position + PnL | Active | YES* | YES | NO | **CONVERT** → `active_predictions` — probability drift tracking |
| `risk_events` table | Paper-trade gate audit log | Active | YES | YES | NO | **CONVERT** → `quality_gate_events` |
| `trade_decisions` table | Bridge between analysis and execution | Active | YES | YES | YES | **CONVERT** → `recommendations`; `position_size_usdc` → `allocation_weight` |

*\* Currently required because the feedback loop uses `realized_pnl > 0` as the correctness signal. See Task 7 §5 for the architectural change that removes this dependency.*

---

## TASK 7: EXECUTIVE VERDICT

### 1. Can LIMWANPO AI become a Professional Polymarket Probability Analysis Platform WITHOUT deleting Layers 6–11?

**YES.**

Evidence: Layers 6–11 (StrategyEngine, RiskEngine, ExecutionEngine, PositionService, ExitEngine, PortfolioService) contain zero live exchange interaction. `clob_client.py` has no POST methods. No wallet SDK exists. No private key is used anywhere. The entire execution chain is self-contained within the local PostgreSQL database.

More importantly, **deleting** Layers 6–11 would break the system's ability to learn. The `OutcomeLearningService` currently determines whether a prediction was `correct` by reading `realized_pnl` from a closed `positions` row. Without that row, `correct = NULL`, and `ConfidenceCalibrationService`, `DynamicWeightService`, and `EnginePerformanceService` receive no usable input. The layers that carry trading vocabulary are the same layers that feed the AI's self-improvement loop.

The path to a probability analysis platform is therefore **conversion, not deletion**.

---

### 2. Which modules only require semantic renaming?

Modules where behaviour is already correct — only the names carry trading identity:

| Current Name | Rename To |
|---|---|
| `StrategyEngine` | `RecommendationEngine` |
| `RiskEngine` | `QualityGate` |
| `ExecutionEngine` | `PredictionCommitEngine` |
| `PositionTrackingService` | `PredictionTrackingService` |
| `PortfolioService` | `AnalyticsService` |
| `CapitalManagementService` | `RecommendationBudgetService` |
| `PositionSizingService` | `AllocationWeightService` |
| `TradeReplayService` | `PredictionReplayService` |
| DB table `orders` | `prediction_commits` |
| DB table `positions` | `active_predictions` |
| DB table `risk_events` | `quality_gate_events` |
| DB table `trade_decisions` | `recommendations` |
| DB table `trade_evaluations` | `prediction_evaluations` |
| DB column `position_size_usdc` | `allocation_weight` |
| DB column `fill_price` | `commit_probability` |
| DB column `peak_pnl_usdc` | `peak_probability_drift` |
| DB column `realized_pnl` (in `positions`) | `resolved_probability_drift` |
| API path `/strategies/active` | `/recommendations/active` |
| API path `/orders/open` | `/predictions/active` |
| API path `/positions/stats` | `/predictions/stats` |
| API path `/risk/blocked` | `/quality-gate/rejected` |

---

### 3. Which modules require behavioral redesign?

Modules where the **logic itself** must change, not just the name:

| Module | Required change |
|---|---|
| `ExitEngine` — `STOP_LOSS` / `PROFIT_TARGET` triggers | Must be redesigned to trigger on **probability threshold** (e.g., `yes_mid` crosses a confidence boundary) or simply removed in favour of the `EXPIRY_EXIT` trigger alone, since prediction markets resolve to 0/1 at a defined `end_time` |
| `ExitEngine` — `TRAILING_STOP` trigger | Trails on `peak_pnl_usdc` — a trading concept with no direct probability equivalent. Must be redesigned as a "confidence deterioration" tracker (e.g., close if `yes_mid` has moved adversely more than X% from commit probability) |
| `ExitEngine` — `SIGNAL_INVALIDATION` trigger | Currently fires when `signal_count_1h == 0`. Should be redesigned to reflect **confidence degradation** (all engines agree confidence has dropped below threshold) |
| `OutcomeLearningService` — correctness logic | Currently uses `realized_pnl > 0` from a closed paper position. Must be redesigned to fetch the actual binary resolution from the Polymarket Gamma API (`GET /events?condition_id=...`) and compare it directly to the AI's `decision_logs.decision` field. This change severs the only structural coupling between trading and learning. |
| `PortfolioService` / `PerformanceAnalyticsService` | Must be redesigned to report accuracy rate, Brier score, and calibration metrics rather than USDC P&L, ROI, and capital metrics |
| `CapitalManagementService` | DAILY_LOSS / WEEKLY_LOSS / MAX_DRAWDOWN rules are dollar-loss limits with no probability equivalent. Must be redesigned as prediction coverage rules (max active predictions, concentration per asset) |

---

### 4. Which modules are unnecessary?

Modules that have **no role** in a probability analysis platform:

| Module / Element | Why unnecessary |
|---|---|
| `_compute_fee()` in `execution_engine.py` | Fees are a trading concept. Returns 0.0 by default already. Remove entirely. |
| `entry_fee_usdc` / `exit_fee_usdc` columns in `orders` | No fees to track in a prediction platform |
| `DAILY_TRADES` risk rule in `risk_engine.py` | Trading frequency limit; irrelevant for prediction management |
| `DAILY_LOSS` / `WEEKLY_LOSS` risk rules | Dollar-loss limits; irrelevant without real capital |
| Trailing stop `peak_pnl_usdc` tracking in `position_service.py` | Pure trading construct if TRAILING_STOP trigger is redesigned |

---

### 5. What is the minimum architecture needed to preserve all AI intelligence while completely removing the Trading Bot identity?

The minimum architecture preserves the complete intelligence stack — all scoring, consensus, learning, calibration, and weight optimisation — while replacing the single structural coupling point (PnL-based correctness) with a direct market resolution lookup.

```
Layer 1:  MarketUniverseService (market_universe_service.py)
          → Syncs active prediction markets from Gamma API

Layer 2:  MarketPriceService (market_price_service.py) + clob_client.py
          → Streams YES/NO probability data from CLOB

Layer 3:  SignalEngine (signal_engine.py) + signal_confidence.py
          → Detects probability movement events; scores confidence and regime

Layer 4:  Nine scoring engines (momentum, trend, volatility, orderbook,
          funding, news, market quality, market context, binance data)
          → Each produces a typed probability score for each active market

Layer 5:  OpportunityEngine (opportunity_engine.py)
          → Ranks markets by analytical attractiveness (composite 0–100)

Layer 5b: DecisionEngine (decision_engine.py) — decide() + _compute_consensus()
          → Emits BUY_YES / BUY_NO / WAIT consensus verdict into decision_logs

Layer 6*: RecommendationEngine (strategy_engine.py renamed)
          → Records which markets the AI is actively predicting (recommendations table)

Layer 7*: QualityGate (risk_engine.py renamed, evaluate() method)
          → Deduplicates and limits active prediction coverage

Layer 8*: PredictionTracker (position_service.py renamed)
          → Tracks probability drift (current yes_mid vs. commit probability) per prediction

Layer 9*: PredictionExpiryMonitor (exit_engine.py redesigned)
          → Closes predictions at market end_time (EXPIRY_EXIT only)
          → Confidence-deterioration close (redesigned SIGNAL_INVALIDATION)
          → STOP_LOSS / PROFIT_TARGET / TRAILING_STOP triggers: REMOVED or redesigned

Layer 10: OutcomeLearningService (outcome_learning_service.py — correctness redesigned)
          → Fetches actual binary resolution from Gamma API
          → Compares to decision_logs.decision directly
          → Populates outcome_learnings.correct WITHOUT requiring a closed position

Layer 11: ConfidenceCalibrationService (confidence_calibration_service.py)
          → ECE/ACE calibration across confidence buckets

Layer 12: DynamicWeightService (dynamic_weight_service.py)
          → Reweights engines by per-engine accuracy

Layer 13: EnginePerformanceService + EngineScorecardService
          → Per-engine hit rate and scorecard

Removed:  _compute_fee(), fee columns, DAILY_LOSS/WEEKLY_LOSS/DAILY_TRADES rules,
          peak_pnl_usdc trailing logic, all USDC/wallet/settlement references,
          pnl_efficiency (replace with probability_drift_efficiency)
```

The key architectural change is **Layer 10**: replacing `realized_pnl > 0` (paper trade result) with a direct Polymarket resolution lookup. This single change severs the dependency of the AI feedback loop on the execution pipeline, after which Layers 6–9 become pure prediction lifecycle management with no trading identity remaining in their logic.

---

## SUMMARY

LIMWANPO AI has functionally **already evolved into a Probability Analysis Platform**. The execution layers (6–11) contain no live exchange interaction and serve exclusively as a structured feedback mechanism for the AI intelligence core. The system's trading identity is **surface-level**: naming conventions, column names, and API paths.

**One structural coupling point exists** and must be addressed: `OutcomeLearningService` currently determines prediction correctness from `realized_pnl > 0` on a closed paper position. This can be replaced with a direct Gamma API resolution lookup without changing any other component.

Beyond that single change, the transformation to a Professional Polymarket Probability Analysis Platform requires:
- **12 modules renamed** (no logic changes)
- **6 modules behaviorally redesigned** (exit triggers, portfolio metrics, capital management, outcome correctness)
- **5 elements removed** (fee logic, trading-frequency rules, dollar-loss limits)
- **0 modules deleted** from the intelligence core (Layers 1–5 and the learning stack)

---

*Audit produced by static code analysis only. No source code was modified.*  
*All file names, class names, method names, and column names verified against actual codebase.*
