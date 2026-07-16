# LIMWANPO AI — IDENTITY CONFLICT REPORT
**Date:** 2026-07-07  
**Platform Identity:** Professional Polymarket Probability Analysis Platform  
**Assumption:** LIMWANPO AI is NOT a Trading Bot.  
**Source:** Static analysis of all services/, models/, schemas/, repositories/, api/v1/, workers/, static/index.html

---

## Classification Key

| Code | Meaning |
|---|---|
| **KEEP** | Term is valid in a probability analysis platform — no rename needed |
| **RENAME** | Term carries trading identity but the underlying concept is valid — rename only |
| **REMOVE** | Term has no equivalent concept in probability analysis — eliminate entirely |

---

## TERM-BY-TERM AUDIT

---

### `trade` / `TradeDecision`

| Property | Detail |
|---|---|
| **Found in** | `models/trade_decision.py`, `repositories/trade_decision_repository.py`, `services/strategy_engine.py`, `api/v1/strategies.py`, `api/v1/trades.py`, `index.html` (AI Activity feed messages) |
| **Specific identifiers** | `TradeDecision` class, `trade_decisions` table, `OPEN_LONG_YES`, `OPEN_LONG_NO` decision values, `/api/v1/strategies`, `/api/v1/trades` endpoints |
| **Concept** | A structured recommendation record — which market, which direction, at what probability |
| **Classification** | **RENAME** |
| **→ Becomes** | `Recommendation` / `ProbabilityRecommendation` / `recommendations` table |
| **Logic change required** | NO — field structure unchanged; only names change |

---

### `order` / `Order`

| Property | Detail |
|---|---|
| **Found in** | `models/order.py`, `repositories/order_repository.py`, `services/execution_engine.py`, `api/v1/orders.py` |
| **Specific identifiers** | `Order` model, `orders` table, `order_repository.create_order()`, `fill_price`, `entry_fee_usdc`, `exit_fee_usdc`, statuses `PENDING`/`FILLED`/`CANCELLED`/`FAILED`, `/api/v1/orders` endpoints |
| **Concept** | A committed, timestamped probability recommendation with a recorded entry probability |
| **Classification** | **RENAME** |
| **→ Becomes** | `PredictionCommit` / `prediction_commits` table; `fill_price` → `commit_probability`; `entry_fee_usdc` / `exit_fee_usdc` → **REMOVE** (see fee section) |
| **Logic change required** | Minimal — fee fields removed; fill price renamed |

---

### `position` / `Position`

| Property | Detail |
|---|---|
| **Found in** | `models/position.py`, `repositories/position_repository.py`, `services/position_service.py`, `api/v1/positions.py`, `index.html` (`openPos[]`, `#p-open` label, `.asset-pos-compact`) |
| **Specific identifiers** | `Position` model, `positions` table, `get_open_positions()`, `close_position()`, `side` (`LONG_YES`/`LONG_NO`), `entry_price`, `current_price`, `unrealized_pnl`, `realized_pnl`, `peak_pnl_usdc`, `status` (OPEN/CLOSED), `capital` field |
| **Concept** | An active prediction record tracking the AI's live probability view |
| **Classification** | **RENAME** |
| **→ Becomes** | `ActivePrediction` / `active_predictions` table; `entry_price` → `commit_probability`; `current_price` → `current_probability`; `side` (LONG_YES/LONG_NO) → `direction` (YES/NO); `status` OPEN/CLOSED → ACTIVE/RESOLVED |
| **Logic change required** | `side` enum rename; status enum rename |

---

### `execution` / `ExecutionEngine`

| Property | Detail |
|---|---|
| **Found in** | `services/execution_engine.py`, `workers/engine_workers.py` (run_execution_engine_loop), `api/v1/health.py` (heartbeat key `execution_engine`), `index.html` (pipeline node "Execution", `ENGINE_NAMES_SHORT.execution_engine`, `NODE_COLS.Execution`, `BADGE_COLS.EXEC/EXECUTED`) |
| **Specific identifiers** | `ExecutionEngine` class, `run_execution_engine_loop`, heartbeat key, UI pipeline node |
| **Concept** | The engine that commits a probability recommendation to a permanent record |
| **Classification** | **RENAME** |
| **→ Becomes** | `PredictionCommitEngine` / `run_prediction_commit_loop`; pipeline node → "COMMIT" |
| **Logic change required** | NO for core logic; fee calculation removed (see below) |

---

### `portfolio` / `PortfolioService`

| Property | Detail |
|---|---|
| **Found in** | `services/portfolio_service.py`, `services/portfolio_allocation_service.py`, `repositories/portfolio_repository.py`, `api/v1/portfolio.py`, `index.html` (`#port-panel`, `loadPortfolio()`) |
| **Specific identifiers** | `PortfolioService`, `portfolio_repository`, `get_pnl_summary()`, `get_portfolio_summary()`, `/api/v1/portfolio/*` |
| **Concept** | Dashboard panel showing current prediction state and historical accuracy |
| **Classification** | **RENAME** |
| **→ Becomes** | `AnalyticsService` / `PredictionDashboardService`; `/api/v1/analytics/*` (partially exists already) |
| **Logic change required** | YES — PnL-based metrics replaced with accuracy-rate metrics (see FINAL_ARCHITECTURE_DECISION.md) |

---

### `risk` / `RiskEngine` / `RiskEvent`

| Property | Detail |
|---|---|
| **Found in** | `services/risk_engine.py`, `repositories/risk_repository.py`, `models/risk_event.py` (implied), `api/v1/risk.py`, `index.html` (`BADGE_COLS.RISK`, pipeline node "Risk", AI Activity feed "Risk rules: DUPLICATE...") |
| **Specific identifiers** | `RiskEngine.evaluate()`, `risk_events` table, `BLOCKED`/`RISK_APPROVED` statuses, `/api/v1/risk/blocked`, UI label "Risk" in pipeline |
| **Concept** | A quality gate preventing duplicate recommendations and enforcing coverage limits |
| **Classification** | **RENAME** |
| **→ Becomes** | `QualityGate` / `GateEngine`; `risk_events` → `quality_gate_events`; `BLOCKED` → `REJECTED`; `RISK_APPROVED` → `APPROVED`; pipeline node → "GATE" |
| **Logic change required** | Partial — dollar-loss rules redesigned (see FINAL_ARCHITECTURE_DECISION.md) |

---

### `capital` / `CapitalManagementService`

| Property | Detail |
|---|---|
| **Found in** | `services/capital_management_service.py`, called by `risk_engine.py`, `api/v1/analytics.py` (`/capital` endpoint), `index.html` (`#p-capital` label "Capital", `loadPortfolio()` reads `/analytics/capital`) |
| **Specific identifiers** | `CapitalManagementService.evaluate()`, `DAILY_LOSS_LIMIT`, `WEEKLY_LOSS_LIMIT`, `LOSS_STREAK_LIMIT`, `MAX_DRAWDOWN_LIMIT`, `daily_pnl`, `drawdown_percent` |
| **Concept** | A recommendation budget service — limits how many active predictions can exist |
| **Classification** | **RENAME** |
| **→ Becomes** | `RecommendationBudgetService`; rules renamed to DAILY_RECOMMENDATION_LIMIT, MAX_ACTIVE_PREDICTIONS, etc. |
| **Logic change required** | YES — dollar-loss rules replaced with prediction-count/coverage rules |

---

### `pnl` / `realized_pnl` / `unrealized_pnl`

| Property | Detail |
|---|---|
| **Found in** | `models/position.py` (columns), `services/position_service.py` (`recalculate_pnl()`, `close_position()`), `repositories/portfolio_repository.py`, `api/v1/portfolio.py`, `index.html` (`#p-dpnl`, `#p-stake`, `pnlD.total_realized_pnl`, `totalUnrPnl`) |
| **Specific identifiers** | `realized_pnl`, `unrealized_pnl`, `total_realized_pnl`, `total_unrealized_pnl`, `peak_pnl_usdc`, `actual_pnl` (in `outcome_learnings`) |
| **Concept** | `unrealized_pnl` ≈ probability drift from commit to now. `realized_pnl` ≈ final probability at resolution vs. commit probability. Both are meaningful in probability context. |
| **Classification** | **RENAME** |
| **→ Becomes** | `unrealized_pnl` → `probability_drift`; `realized_pnl` → `resolution_delta`; `peak_pnl_usdc` → `peak_drift`; `actual_pnl` in outcome_learnings → `resolution_value` |
| **Logic change required** | NO for unrealized/current tracking. YES for `realized_pnl` correctness logic in OutcomeLearningService (see Phase 3 Decision Audit). |

---

### `exposure`

| Property | Detail |
|---|---|
| **Found in** | `services/risk_engine.py` (rule `MAX_EXPOSURE`), `api/v1/portfolio.py`, `index.html` (`#p-used` label "Exposure", `.asset-pos-compact` "$X Exp") |
| **Specific identifiers** | `MAX_EXPOSURE` rule, `ASSET_EXPOSURE_LIMIT`, `capitalUsed` in JS, `p-used-s` subtitle |
| **Concept** | The count or weight of active predictions for a given asset |
| **Classification** | **RENAME** |
| **→ Becomes** | `coverage` / `active_coverage`; `MAX_EXPOSURE` → `MAX_COVERAGE_PER_ASSET`; UI label "Exposure" → "Coverage" |
| **Logic change required** | NO — same counting logic, renamed |

---

### `win_rate`

| Property | Detail |
|---|---|
| **Found in** | `services/performance_analytics_service.py`, `api/v1/analytics.py`, `index.html` (`analyticsData.win_rate`, `#p-wr` label "Prediction Accuracy", `#p-wr-s` subtitle) |
| **Specific identifiers** | `win_rate` field in analytics response, UI label already says "Prediction Accuracy" |
| **Concept** | Prediction accuracy rate — already correctly named in the UI |
| **Classification** | **RENAME** |
| **→ Becomes** | `prediction_accuracy` / `accuracy_rate`; UI label already correct ("Prediction Accuracy") |
| **Logic change required** | NO — same computation; field name change only |

---

### `drawdown`

| Property | Detail |
|---|---|
| **Found in** | `services/capital_management_service.py` (`MAX_DRAWDOWN_LIMIT`), `api/v1/analytics.py` (`drawdown_percent`), `index.html` (`analyticsData.drawdown_percent`) |
| **Specific identifiers** | `drawdown_percent`, `MAX_DRAWDOWN_LIMIT` rule |
| **Concept** | Consecutive wrong predictions / accuracy degradation |
| **Classification** | **RENAME** |
| **→ Becomes** | `accuracy_degradation` / `prediction_slump`; `MAX_DRAWDOWN_LIMIT` → `MAX_CONSECUTIVE_MISS_LIMIT` |
| **Logic change required** | YES — computed from P&L currently; redesign to count consecutive incorrect predictions |

---

### `stop_loss` / `take_profit` / `trailing_stop`

| Property | Detail |
|---|---|
| **Found in** | `services/exit_engine.py` (trigger branches: `EXIT_STOP_LOSS`, `EXIT_PROFIT_TARGET`, `TRAILING_STOP`), `config/settings.py` (threshold values) |
| **Specific identifiers** | `EXIT_STOP_LOSS`, `EXIT_PROFIT_TARGET`, `TRAILING_STOP` trigger types, `peak_pnl_usdc` trailing reference |
| **Concept in probability platform** | STOP_LOSS / PROFIT_TARGET have no direct equivalent — prediction markets resolve at 0 or 1, not at price thresholds. TRAILING_STOP approximates "close if confidence has deteriorated." |
| **Classification** | `EXIT_STOP_LOSS` → **REMOVE**; `EXIT_PROFIT_TARGET` → **REMOVE**; `TRAILING_STOP` → **RENAME** → `CONFIDENCE_DETERIORATION` |
| **Logic change required** | YES — STOP_LOSS and PROFIT_TARGET triggers must be deleted; TRAILING_STOP logic replaced |

---

### `fill_price` / `entry_price`

| Property | Detail |
|---|---|
| **Found in** | `models/order.py` (`fill_price` column), `models/position.py` (`entry_price` column), `services/execution_engine.py` (`_execute_decision()` sets fill from `yes_ask`/`yes_bid`), `index.html` (`entryPct` — displays `pos.entry_price * 100` as percentage) |
| **Specific identifiers** | `fill_price`, `entry_price`, `yes_ask` / `yes_bid` used to compute fill |
| **Concept** | The Polymarket probability at the moment the recommendation was committed |
| **Classification** | **RENAME** |
| **→ Becomes** | `commit_probability`; already a probability value (0–1); no computation change needed |
| **Logic change required** | NO |

---

### `entry_fee_usdc` / `exit_fee_usdc` / `_compute_fee()`

| Property | Detail |
|---|---|
| **Found in** | `models/order.py` (columns), `services/execution_engine.py` (`_compute_fee()` function — returns 0.0 by default in paper mode) |
| **Concept** | Transaction costs — irrelevant in a probability analysis platform that has no real exchange |
| **Classification** | **REMOVE** |
| **Logic change required** | Delete `_compute_fee()`, remove `entry_fee_usdc` and `exit_fee_usdc` columns from `orders` / `prediction_commits` table |

---

### `position_size_usdc`

| Property | Detail |
|---|---|
| **Found in** | `models/trade_decision.py` (column), `services/strategy_engine.py` (set by `position_sizing_service.py`), `services/position_sizing_service.py` |
| **Specific identifiers** | `position_size_usdc` column, `PositionSizingService` class |
| **Concept** | Confidence-proportional allocation weight for the recommendation |
| **Classification** | **RENAME** |
| **→ Becomes** | `allocation_weight` (float 0.0–1.0); `PositionSizingService` → `AllocationWeightService` |
| **Logic change required** | Partial — computation logic stays; USDC denomination removed |

---

### `LONG_YES` / `LONG_NO`

| Property | Detail |
|---|---|
| **Found in** | `models/position.py` (`side` enum), `services/execution_engine.py` (branch conditions), `index.html` (`rawSide === "LONG_YES"` → normalized to "YES") |
| **Specific identifiers** | `LONG_YES`, `LONG_NO` as position `side` values |
| **Concept** | The direction of the probability prediction: YES or NO |
| **Classification** | **RENAME** |
| **→ Becomes** | `YES` / `NO` directly; the frontend already normalises these in `normSide` — making them canonical simplifies the codebase |
| **Logic change required** | Enum rename + DB migration |

---

### `FILLED` / `RISK_APPROVED` / `BLOCKED`

| Property | Detail |
|---|---|
| **Found in** | `models/order.py` (`FILLED` status), `models/trade_decision.py` (`RISK_APPROVED`, `BLOCKED` statuses), `services/execution_engine.py`, `services/risk_engine.py`, `api/v1/risk.py` |
| **Specific identifiers** | Status enum values in DB and service logic |
| **Concept** | Lifecycle states of a recommendation |
| **Classification** | **RENAME** |
| **→ Becomes** | `FILLED` → `COMMITTED`; `RISK_APPROVED` → `APPROVED`; `BLOCKED` → `REJECTED` |
| **Logic change required** | Enum rename + DB migration for status columns |

---

### `paper_mode` / `PAPER MODE`

| Property | Detail |
|---|---|
| **Found in** | `config/settings.py` (`EXECUTION_PAPER_MODE=true`), `index.html` (header badge "PAPER MODE", AI Activity feed "paper trading mode") |
| **Specific identifiers** | `EXECUTION_PAPER_MODE` env var, UI badge |
| **Concept** | The system never executes real trades — this is always true for a probability platform |
| **Classification** | **REMOVE** |
| **→ Becomes** | Remove the paper mode flag entirely — the concept doesn't apply. UI badge "PAPER MODE" → remove or replace with "ANALYSIS MODE" |
| **Logic change required** | Remove flag and any conditional branches on it |

---

### `broker` / wallet / settlement

| Property | Detail |
|---|---|
| **Found in** | NOT FOUND — no broker API, no wallet SDK, no on-chain settlement logic anywhere in the codebase |
| **Classification** | **KEEP** (as absent) — nothing to remove |

---

### `open_position` / `close_position`

| Property | Detail |
|---|---|
| **Found in** | `repositories/position_repository.py` (`get_open_positions()`), `services/position_service.py` (`close_position()`), `api/v1/positions.py`, `index.html` (`fetch("/api/v1/positions/open")`) |
| **Specific identifiers** | Function names `close_position()`, `get_open_positions()`, endpoint `/positions/open` |
| **Classification** | **RENAME** |
| **→ Becomes** | `get_active_predictions()`, `resolve_prediction()`, `/predictions/active` |
| **Logic change required** | NO — same lifecycle logic; names only |

---

## SUMMARY TABLE

| Trading Term | Files Affected | Classification | Rename To / Action |
|---|---|---|---|
| `trade` / `TradeDecision` | models, repos, services, api, UI | **RENAME** | `Recommendation` |
| `order` / `Order` | models, repos, services, api | **RENAME** | `PredictionCommit` |
| `position` / `Position` | models, repos, services, api, UI | **RENAME** | `ActivePrediction` |
| `execution` / `ExecutionEngine` | services, workers, UI | **RENAME** | `PredictionCommitEngine` |
| `portfolio` / `PortfolioService` | services, repos, api, UI | **RENAME** | `AnalyticsService` |
| `risk` / `RiskEngine` / `RiskEvent` | services, repos, api, UI | **RENAME** | `QualityGate` |
| `capital` / `CapitalManagementService` | services, api, UI | **RENAME** | `RecommendationBudgetService` |
| `pnl` / `realized_pnl` / `unrealized_pnl` | models, services, api, UI | **RENAME** | `resolution_delta` / `probability_drift` |
| `exposure` | services, api, UI | **RENAME** | `coverage` |
| `win_rate` | services, api, UI | **RENAME** | `prediction_accuracy` (UI label already correct) |
| `drawdown` | services, api, UI | **RENAME** | `accuracy_degradation` |
| `stop_loss` / `EXIT_STOP_LOSS` | services | **REMOVE** | Delete trigger |
| `take_profit` / `EXIT_PROFIT_TARGET` | services | **REMOVE** | Delete trigger |
| `trailing_stop` / `TRAILING_STOP` | services | **RENAME** | `CONFIDENCE_DETERIORATION` + redesign |
| `fill_price` / `entry_price` | models, services, UI | **RENAME** | `commit_probability` |
| `entry_fee_usdc` / `exit_fee_usdc` | models, services | **REMOVE** | Delete columns + function |
| `_compute_fee()` | services/execution_engine.py | **REMOVE** | Delete function |
| `position_size_usdc` | models, services | **RENAME** | `allocation_weight` |
| `LONG_YES` / `LONG_NO` | models, services, UI | **RENAME** | `YES` / `NO` |
| `FILLED` | models, services | **RENAME** | `COMMITTED` |
| `RISK_APPROVED` | models, services | **RENAME** | `APPROVED` |
| `BLOCKED` | models, services, api, UI | **RENAME** | `REJECTED` |
| `PAPER MODE` / `EXECUTION_PAPER_MODE` | config, UI | **REMOVE** | Concept does not apply |
| `open_position` / `close_position` | repos, services, api | **RENAME** | `activate_prediction` / `resolve_prediction` |
| `broker` / `wallet` / `settlement` | — | **KEEP** (absent) | Does not exist — nothing to do |
| `PositionSizingService` | services | **RENAME** | `AllocationWeightService` |
| `StrategyEngine` | services, workers, UI | **RENAME** | `RecommendationEngine` |
| `ExitEngine` | services, workers | **RENAME** | `PredictionExpiryMonitor` |

---

## COUNTS

| Classification | Count |
|---|---|
| **KEEP** | 1 (broker/wallet/settlement — absent) |
| **RENAME** | 22 terms / identifiers |
| **REMOVE** | 4 (stop_loss trigger, take_profit trigger, fee logic, paper_mode flag) |

**Total identity conflicts identified: 27**  
**No term requires architectural deletion of an intelligence module.**
