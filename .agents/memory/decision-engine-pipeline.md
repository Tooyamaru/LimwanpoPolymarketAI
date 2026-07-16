---
name: Decision Engine pipeline (Phase Next)
description: Rule-based, read-only Signal→Momentum→Trend→Volatility→Opportunity→Risk→Decision pipeline architecture
---

Built as a fully separate, read-only analytical layer on top of the existing trading engines — it never mutates market_universe, positions, orders, or trade_decisions.

**Why:** user brief required "Decision Engine only reads data, never mutates market data" and explicitly froze all dashboard/UI work; the pipeline had to compose with existing Signal/Opportunity/Risk engines without touching their tables.

**How to apply:**
- Momentum/Trend/Volatility engines are independent Binance-kline-based scorers (own client `services/binance_market_data.py`, separate from the frozen `btc_candles.py`/`market_reference_service.py`). Each UPSERTs one row per (asset, timeframe) into its own table (`momentum_scores`, `trend_scores`, `volatility_scores`), mirroring the Opportunity model's "one current row per key" pattern.
- DecisionEngine reads latest Signal (by condition_id), Momentum/Trend/Volatility (by asset+timeframe), Opportunity (by condition_id), plus a **read-only risk context** it computes itself (reusing MAX_OPEN_POSITIONS/MAX_DAILY_TRADES/MAX_DAILY_LOSS settings but never touching risk_engine.py or risk_events) — this avoids coupling to Risk Engine internals while still respecting the same limits.
- Voting model: each directional engine casts vote in {-1,0,+1} weighted by (layer weight × engine's own confidence); risk_score is a hard gate that forces WAIT below RISK_MIN_SCORE regardless of vote. All engines log full reasoning strings; DecisionLog is append-only (mirrors TradeDecision's log pattern).
- All 3 new worker loops + DecisionEngine loop follow the exact `run_X_engine_loop` pattern (startup run + `universe_ready.wait()` gate + `engine_health.record_heartbeat`) already used by every other engine — copy that pattern exactly, don't invent a new one.
