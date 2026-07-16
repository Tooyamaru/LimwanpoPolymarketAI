---
name: Decision Engine Intelligence Upgrade
description: Phase Next upgrade — 8 phases added to Decision Engine: Consensus, Market Quality, Entry Quality, Confidence Engine, Explainability, Decision History, Self-Validation, Engine Health.
---

## What was built

8 phases added to `decision_engine.py`. All backend-only. No ML. No UI changes.

**Phase 1 — Consensus Engine** (`_compute_consensus`):
- Computes `agreement_level` (0.5=split, 1.0=unanimous), `conflict_detected` (>30% weight opposing), `consensus_score` (0-100).
- Stored in `decision_logs`: `consensus_score`, `agreement_level`, `conflict_detected`.

**Phase 2 — Market Quality Filter**:
- Existing NON_TRADABLE_QUALITIES gate + new numeric floor `MIN_MARKET_QUALITY_SCORE=20.0`.
- Score below 20 → WAIT even for AVERAGE-label markets.

**Phase 3 — Entry Quality Engine** (`_compute_entry_quality`):
- Score 0-100: spread quality (±25), price attractiveness (±20), liquidity behaviour (±15), opportunity alignment (±15).
- Gate: `MIN_ENTRY_QUALITY_SCORE=30.0` → WAIT if score below threshold.
- Stored in `decision_logs`: `entry_quality_score`.

**Phase 4 — Confidence Engine** (`_compute_confidence_engine`):
- NOT a weighted average. Six additive components: consensus (0-30), market_quality (0-25), entry_quality (0-20), trend_strength (0-10), momentum_strength (0-10), risk_headroom (0-5).
- Then: × context_multiplier (0.6-1.0), × volatility_factor (0.88-1.04), × conflict_penalty (0.70 if conflict).

**Phase 5 — Explainability**:
- `steps[]` reasoning chain now covers all phases; persisted in `decision_logs.reasons`.

**Phase 6 — Decision History**:
- Was already append-only. No change.

**Phase 7 — Self-Validation** (`_self_validate`):
- Priority-ordered checks: Trend UP + Momentum BEARISH → WAIT; Trend DOWN + Momentum BULLISH → WAIT; spread > 0.08 → WAIT; Low Liquidity behaviour → WAIT; Phase 1 conflict → WAIT.
- Fires BEFORE the final vote_score decision gate.

**Phase 8 — Engine Health** (`get_decision_stats`):
- New stats: `conflict_count`, `consensus_count` (agreement_level ≥ 0.70), `avg_entry_quality`.
- Stats schema (`DecisionStatsResponse`) updated.

## Key constants (decision_engine.py)
```
CONFLICT_AGREEMENT_THRESHOLD = 0.30   # losing-side fraction → conflict
CONFLICT_SPREAD_THRESHOLD    = 0.08   # spread → WAIT
MIN_MARKET_QUALITY_SCORE     = 20.0   # market score floor → WAIT
MIN_ENTRY_QUALITY_SCORE      = 30.0   # entry quality floor → WAIT
EXPENSIVE_PRICE_THRESHOLD    = 0.82   # YES/NO mid → "too expensive"
```

## DB migrations (safe, ADD COLUMN IF NOT EXISTS)
- `decision_logs`: consensus_score, agreement_level, conflict_detected, entry_quality_score
- Index: `ix_decision_conflict` on `conflict_detected`

**Why:** Spec required upgrade from flat weighted-rule to Consensus + Entry Quality + multi-factor Confidence while staying fully deterministic, rule-based, explainable, auditable — no ML.

**How to apply:** If adding new voting engines, always update `_compute_consensus` vote list. If adding new market quality labels, keep `NON_TRADABLE_QUALITIES` in sync between `polymarket_market_engine.py` and `decision_engine.py`.
