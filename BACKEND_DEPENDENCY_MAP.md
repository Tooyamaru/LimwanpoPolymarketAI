# LIMWANPO AI — BACKEND DEPENDENCY MAP
**Date:** 2026-07-07  
**Source:** `backend/app/workers/engine_workers.py`, all services/, repositories/, models/, api/v1/  
**Format:** Engine Worker → Service Class (file) → Repository Class (file) → DB Table(s)

R = READ, W = WRITE

---

## LAYER 1 — MARKET DISCOVERY

```
run_universe_sync_loop (engine_workers.py)
  └─► MarketUniverseService (market_universe_service.py)
        ├── gamma_series_client.py         [External: Polymarket Gamma API — GET only]
        └─► universe_repository.py
              └── market_universe            [W: condition_id, asset, status, end_time,
                                                  timeframe, question, is_active]

run_universe_sync_loop (market reference sub-step)
  └─► market_reference_service.py (fetch_opening_price, resolve_market_reference)
        ├── binance_market_data.py          [External: Binance /api/v3/klines — GET only]
        └─► universe_repository.py
              └── market_universe            [W: opening_price field only]
```

---

## LAYER 2 — MARKET PRICE

```
run_price_refresh_loop (engine_workers.py)
  └─► MarketPriceService (market_price_service.py)
        ├── clob_client.py                  [External: Polymarket CLOB /book — GET only]
        └─► market_price_repository.py
              └── market_price_snapshots     [W: condition_id, yes_mid, yes_bid,
                                                  yes_ask, no_mid, spread, timestamp]
```

---

## LAYER 3 — SIGNAL ENGINE

```
run_signal_engine_loop (engine_workers.py)
  └─► SignalEngine (signal_engine.py)
        ├── signal_confidence.py            [compute_confidence(), detect_regime()]
        ├─► market_price_repository.py      [R: market_price_snapshots — current + prev]
        ├─► universe_repository.py          [R: market_universe — active conditions]
        └─► signal_repository.py
              └── signals                    [W: condition_id, asset, timeframe,
                                                  yes_mid_before, yes_mid_after,
                                                  yes_mid_delta, spread_delta,
                                                  seed_deviation, severity,
                                                  confidence_score, regime,
                                                  mtf_confirmed]
```

---

## LAYER 4a — MOMENTUM ENGINE

```
run_momentum_engine_loop (engine_workers.py)
  └─► MomentumEngine (momentum_engine.py)
        ├── binance_market_data.py          [External: Binance klines — GET only]
        └─► momentum_repository.py
              └── momentum_scores            [W: asset, timeframe, score, confidence,
                                                  direction, reason, computed_at]
```

## LAYER 4b — TREND ENGINE

```
run_trend_engine_loop (engine_workers.py)
  └─► TrendEngine (trend_engine.py)
        ├── binance_market_data.py          [External: Binance klines — GET only]
        └─► trend_repository.py
              └── trend_scores               [W: asset, timeframe, score, confidence,
                                                  direction, reason, computed_at]
```

## LAYER 4c — VOLATILITY ENGINE

```
run_volatility_engine_loop (engine_workers.py)
  └─► VolatilityEngine (volatility_engine.py)
        ├── binance_market_data.py          [External: Binance klines — GET only]
        └─► volatility_repository.py
              └── volatility_scores          [W: asset, timeframe, score, confidence,
                                                  regime, reason, computed_at]
```

## LAYER 4d — ORDERBOOK ENGINE

```
run_orderbook_engine_loop (engine_workers.py) [if exists, or called within price loop]
  └─► OrderbookEngine (orderbook_engine.py)
        ├── clob_client.py                  [External: Polymarket CLOB — GET only]
        └─► orderbook_repository.py
              └── orderbook_scores           [W: asset, direction, confidence,
                                                  bid_volume, ask_volume,
                                                  imbalance_pct, computed_at]
```

## LAYER 4e — FUNDING ENGINE

```
  └─► FundingEngine (funding_engine.py)
        └─► funding_repository.py
              └── funding_scores             [W: asset, rate, prediction,
                                                  confidence, computed_at]
```

## LAYER 4f — NEWS ENGINE

```
  └─► NewsEngine (news_engine.py)
        └─► news_repository.py
              └── news_scores                [W: asset, sentiment, confidence,
                                                  impact, computed_at]
```

## LAYER 4g — MARKET QUALITY / BEHAVIOUR ENGINE

```
  └─► PolymarketMarketEngine (polymarket_market_engine.py)
        ├─► market_quality_repository.py
        │     └── market_quality_scores      [W: condition_id, asset, score,
        │                                         market_behaviours, computed_at]
        └─► market_context_repository.py
              └── market_context_scores      [W: asset, status, confidence,
                                                  computed_at]
```

---

## LAYER 5 — OPPORTUNITY ENGINE

```
run_opportunity_engine_loop (engine_workers.py)
  └─► OpportunityEngine (opportunity_engine.py)
        ├─► momentum_repository.py           [R: momentum_scores]
        ├─► trend_repository.py              [R: trend_scores]
        ├─► volatility_repository.py         [R: volatility_scores]
        ├─► signal_repository.py             [R: signals]
        ├─► universe_repository.py           [R: market_universe]
        └─► opportunity_repository.py
              └── opportunities              [W: condition_id, asset, timeframe,
                                                  opportunity_score, direction,
                                                  priority_score, reason,
                                                  computed_at]
```

---

## LAYER 5b — DECISION ENGINE

```
run_decision_engine_loop (engine_workers.py)
  └─► DecisionEngine (decision_engine.py)
        │  Key methods: decide(), _decide_market(), _compute_consensus(),
        │               _load_effective_weights(), _interpret_*(), _get_*()
        ├─► signal_repository.py             [R: signals]
        ├─► momentum_repository.py           [R: momentum_scores]
        ├─► trend_repository.py              [R: trend_scores]
        ├─► volatility_repository.py         [R: volatility_scores]
        ├─► opportunity_repository.py        [R: opportunities]
        ├─► orderbook_repository.py          [R: orderbook_scores]
        ├─► funding_repository.py            [R: funding_scores]
        ├─► news_repository.py               [R: news_scores]
        ├─► market_quality_repository.py     [R: market_quality_scores]
        ├─► market_context_repository.py     [R: market_context_scores]
        ├─► engine_weight_repository.py      [R: engine_weights]
        ├─► universe_repository.py           [R: market_universe]
        └─► decision_repository.py
              └── decision_logs              [W: condition_id, asset, timeframe,
                                                  decision (BUY_YES/BUY_NO/WAIT),
                                                  confidence, vote_score,
                                                  consensus_score, agreement_level,
                                                  conflict_detected, entry_quality_score,
                                                  per-engine score columns,
                                                  supporting_engines, reasons]
```

---

## LAYER 6 — STRATEGY ENGINE

```
run_strategy_engine_loop (engine_workers.py)
  └─► StrategyEngine (strategy_engine.py)
        ├─► opportunity_repository.py        [R: opportunities]
        ├─► signal_repository.py             [R: signals — confidence gate]
        ├─► position_repository.py           [R: positions — duplicate check]
        ├── position_sizing_service.py       [computes position_size_usdc]
        └─► trade_decision_repository.py
              └── trade_decisions            [W: condition_id, asset, timeframe,
                                                  decision (OPEN_LONG_YES/NO),
                                                  status (PENDING/WATCH/SKIP),
                                                  opportunity_score, direction,
                                                  yes_mid, yes_bid, yes_ask,
                                                  spread_yes, position_size_usdc,
                                                  decided_at]
```

---

## LAYER 7 — RISK ENGINE

```
run_risk_engine_loop (engine_workers.py)
  └─► RiskEngine (risk_engine.py)  [main method: evaluate()]
        ├── capital_management_service.py    [DAILY_LOSS_LIMIT, WEEKLY_LOSS_LIMIT,
        │                                     LOSS_STREAK_LIMIT, MAX_DRAWDOWN_LIMIT]
        ├─► trade_decision_repository.py     [R: trade_decisions WHERE status=PENDING]
        ├─► position_repository.py           [R: positions — open count, exposure]
        ├─► order_repository.py              [R: orders — daily_trades count]
        └─► trade_decision_repository.py     [W: trade_decisions.status →
        └─► risk_repository.py                    RISK_APPROVED or BLOCKED]
              └── risk_events                [W: asset, event_type, severity,
                                                  message, timestamp]
```

---

## LAYER 8 — EXECUTION ENGINE  *(Paper Mode Only)*

```
run_execution_engine_loop (engine_workers.py)
  └─► ExecutionEngine (execution_engine.py)  [main method: run()]
        │  Methods: _execute_decision(), _execute_close_decision(), _compute_fee()
        │  NO external API calls — fills computed from internal snapshots only
        ├─► trade_decision_repository.py     [R: trade_decisions WHERE
        │                                         status=RISK_APPROVED]
        ├─► market_price_repository.py       [R: market_price_snapshots —
        │                                         yes_ask/yes_bid for fill price]
        └─► order_repository.py
              └── orders                     [W: decision_id, condition_id,
                                                  asset, timeframe, side,
                                                  order_type, quantity,
                                                  fill_price, status (FILLED),
                                                  entry_fee_usdc, exit_fee_usdc]
```

---

## LAYER 9 — POSITION TRACKING SERVICE  *(Paper Mode Only)*

```
run_position_tracking_loop (engine_workers.py)
  └─► PositionTrackingService (position_service.py)
        │  Methods: create_position_from_fill(), update_market_prices(),
        │           recalculate_pnl(), close_position()
        ├─► order_repository.py              [R: orders WHERE status=FILLED]
        ├─► opportunity_repository.py        [R: opportunities — yes_mid for
        │                                         current_price update]
        └─► position_repository.py
              └── positions                  [W: asset, side (LONG_YES/LONG_NO),
                                                  size, entry_price, current_price,
                                                  unrealized_pnl, realized_pnl,
                                                  peak_pnl_usdc, status
                                                  (OPEN/CLOSED), condition_id,
                                                  opened_at, closed_at]
```

---

## LAYER 10 — EXIT ENGINE  *(Paper Mode Only)*

```
run_exit_engine_loop (engine_workers.py)
  └─► ExitEngine (exit_engine.py)
        │  Triggers: EXPIRY_EXIT, STOP_LOSS, PROFIT_TARGET,
        │            TRAILING_STOP, SIGNAL_INVALIDATION
        ├─► position_repository.py           [R: positions WHERE status=OPEN]
        ├─► universe_repository.py           [R: market_universe — end_time]
        ├─► signal_repository.py             [R: signals — for SIGNAL_INVALIDATION]
        └─► trade_decision_repository.py
              └── trade_decisions            [W: new CLOSE_POSITION row
                                                  with exit_reason, target_position_id]
```

---

## LAYER 11 — OUTCOME LEARNING

```
run_outcome_learning_loop (engine_workers.py)
  └─► OutcomeLearningService (outcome_learning_service.py)
        ├─► universe_repository.py           [R: market_universe WHERE
        │                                         end_time < now, status=active]
        ├─► decision_repository.py           [R: decision_logs — most recent
        │                                         per condition_id at/before end_time]
        ├─► position_repository.py           [R: positions WHERE status=CLOSED,
        │                                         condition_id matches]
        └─► outcome_learning_repository.py
              └── outcome_learnings          [W: condition_id, asset, timeframe,
                                                  prediction, actual_pnl, correct,
                                                  decision_log_id, position_id,
                                                  confidence, consensus_score,
                                                  per-engine direction columns,
                                                  feedback_summary, evaluated_at]
        ⚠  correct = (realized_pnl > 0) from closed position.
           If no closed position exists: correct = NULL.
           NULL rows are EXCLUDED from all downstream calibration.
```

---

## LAYER 12 — CONFIDENCE CALIBRATION

```
[triggered by outcome_learning_loop or scheduled]
  └─► ConfidenceCalibrationService (confidence_calibration_service.py)
        │  Main method: recompute(session)
        ├─► outcome_learning_repository.py   [R: outcome_learnings WHERE
        │                                         confidence IS NOT NULL
        │                                         AND correct IS NOT NULL]
        └─► confidence_calibration_repository.py
              ├── confidence_calibration_buckets  [W: bucket ranges, accuracy,
              │                                        count per 5% bucket]
              └── confidence_calibration_summary  [W: ECE, ACE, over/under/
                                                       well-calibrated %]
```

---

## LAYER 13 — ENGINE PERFORMANCE & DYNAMIC WEIGHTS

```
run_dynamic_weight_loop (engine_workers.py)
  └─► DynamicWeightService (dynamic_weight_service.py)
        ├─► outcome_learning_repository.py   [R: outcome_learnings]
        ├─► engine_performance_repository.py [R/W: engine_performance_stats —
        │                                         accuracy, sample_count]
        └─► engine_weight_repository.py
              └── engine_weights             [W: engine_name, current_weight,
                                                  performance_factor, last_adjusted_at]

  └─► EnginePerformanceService (engine_performance_service.py)
        ├─► outcome_learning_repository.py   [R: outcome_learnings]
        └─► engine_performance_repository.py
              └── engine_performance_stats   [W: engine_name, accuracy,
                                                  sample_count, last_updated]

  └─► EngineScorecardService (engine_scorecard_service.py)
        └─► engine_performance_repository.py [R: engine_performance_stats]
```

---

## LAYER 14 — TRADE EVALUATION  *(Paper Mode Only)*

```
[triggered post-close or on demand]
  └─► TradeEvaluationService (trade_evaluation_service.py)
        ├─► position_repository.py           [R: positions — closed positions]
        ├─► opportunity_repository.py        [R: opportunities at entry time]
        ├─► signal_repository.py             [R: signals at entry time]
        └─► [trade_evaluations table]
              └── trade_evaluations          [W: position_id, entry_quality,
                                                  exit_quality, timing_score,
                                                  pnl_efficiency, quality_score,
                                                  grade, realized_pnl,
                                                  entry_efficiency, hold_minutes,
                                                  close_reason, evaluated_at]
```

---

## LAYER 15 — PORTFOLIO & ANALYTICS

```
[API-only; no worker loop — read-only aggregation]

  └─► PortfolioService (portfolio_service.py)
        └─► portfolio_repository.py          [R: positions, orders,
                                                  trade_decisions, risk_events]

  └─► PortfolioAllocationService (portfolio_allocation_service.py)
        └─► portfolio_repository.py          [R: positions grouped by asset]

  └─► PerformanceAnalyticsService (performance_analytics_service.py)
        └─► position_repository.py           [R: positions — win_rate,
                                                  total_trades, total_fees,
                                                  drawdown computation]

  └─► CapitalManagementService (capital_management_service.py)
        ├─► position_repository.py           [R: positions — daily_pnl,
        │                                         unrealized_pnl]
        └─► order_repository.py              [R: orders — daily_trades]
```

---

## LAYER 16 — WATCHDOG

```
run_watchdog_loop (watchdog.py)
  └─► engine_health.py
        └── Redis heartbeat store          [R: all engine heartbeat timestamps]
        [Action: sys.exit(1) if any engine stalls beyond WATCHDOG_RESTART_SECONDS]
        [No DB repository — reads from Redis only]
```

---

## FULL DATABASE TABLE INVENTORY

| Table | Written By | Read By |
|---|---|---|
| `market_universe` | MarketUniverseService, MarketReferenceService | Every engine (universe gate) |
| `market_price_snapshots` | MarketPriceService | SignalEngine, ExecutionEngine, all FE via /price/active |
| `signals` | SignalEngine | DecisionEngine, StrategyEngine, ExitEngine, OpportunityEngine, TradeEvaluationService, FE |
| `momentum_scores` | MomentumEngine | OpportunityEngine, DecisionEngine |
| `trend_scores` | TrendEngine | OpportunityEngine, DecisionEngine |
| `volatility_scores` | VolatilityEngine | OpportunityEngine, DecisionEngine |
| `orderbook_scores` | OrderbookEngine | DecisionEngine |
| `funding_scores` | FundingEngine | DecisionEngine |
| `news_scores` | NewsEngine | DecisionEngine |
| `market_quality_scores` | PolymarketMarketEngine | DecisionEngine |
| `market_context_scores` | PolymarketMarketEngine | DecisionEngine |
| `opportunities` | OpportunityEngine | StrategyEngine, PositionTrackingService, FE |
| `decision_logs` | DecisionEngine | OutcomeLearningService |
| `trade_decisions` | StrategyEngine, ExitEngine | RiskEngine, ExecutionEngine, PortfolioService |
| `risk_events` | RiskEngine | PortfolioService |
| `orders` | ExecutionEngine | PositionTrackingService, RiskEngine, PortfolioService, CapitalManagementService |
| `positions` | PositionTrackingService | ExitEngine, RiskEngine, PortfolioService, OutcomeLearningService, TradeEvaluationService, PerformanceAnalyticsService, CapitalManagementService, FE |
| `outcome_learnings` | OutcomeLearningService | ConfidenceCalibrationService, DynamicWeightService, EnginePerformanceService |
| `confidence_calibration_buckets` | ConfidenceCalibrationService | Dashboard (indirectly via health) |
| `confidence_calibration_summary` | ConfidenceCalibrationService | DynamicWeightService |
| `engine_performance_stats` | EnginePerformanceService | DynamicWeightService, EngineScorecardService |
| `engine_weights` | DynamicWeightService | DecisionEngine |
| `trade_evaluations` | TradeEvaluationService | Evaluation API endpoints |
| `market_type_performance` | MarketTypePerformanceService | Analytics endpoints |
