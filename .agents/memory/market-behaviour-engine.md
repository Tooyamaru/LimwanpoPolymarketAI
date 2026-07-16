---
name: Market Behaviour Engine (Phase Next)
description: Architecture and key decisions for the Market Behaviour Engine upgrade — behaviour detection, quality classification, and decision reasoning.
---

## What was upgraded
- `polymarket_market_engine.py` — now reads last 5 snapshots (BEHAVIOUR_WINDOW=5) to detect directional behaviour labels instead of just scoring a single snapshot
- `decision_engine.py` — now produces 10-step human-readable reasoning chain (trader-style) instead of a flat score sum

## Behaviour labels produced
Trend labels (require ≥3 data points): Increasing Liquidity, Decreasing Liquidity, High Participation, Low Participation, Market becoming more efficient
Point-in-time labels (single snapshot OK): Healthy Spread, Wide Spread, Low Liquidity
Dynamics labels (require ≥2 snapshots): Aggressive Buyers, Buy Pressure, Aggressive Sellers, Sell Pressure, Balanced Market, Sellers Weakening
Composite (derived): Market Stability, Passive Market

**Why:** Using trend labels from single snapshots creates false non-tradable classifications. Low Liquidity is the correct point-in-time label; Decreasing Liquidity requires 3 snapshots showing consistent decline.

## Quality classification hierarchy (Phase 3)
Non-tradable: High Risk (near expiry), Illiquid (Wide Spread + Low Participation/Low Liquidity), Avoid (Decreasing/Low Liquidity + Wide Spread)
Tradable: Excellent (3+ positive, 0 negative), Healthy (2+ positive, 0 negative), GOOD (1+ positive, ≤1 negative), AVERAGE (mixed), BAD (2+ negative)

NON_TRADABLE_QUALITIES = {"BAD", "High Risk", "Illiquid", "Avoid"} — shared constant, must match in both engines.

## Decision Engine reasoning pipeline
Step 1: Market Behaviour → PRIMARY GATE (forces WAIT if non-tradable OR if no data at all)
Step 2: Spread interpretation
Step 3: Buy/Sell pressure from behaviour labels
Step 4: Orderbook confirmation
Step 5: Funding rate
Step 6: Momentum
Step 7: Trend
Step 8: Market Context (confidence multiplier)
Step 9: Risk (hard gate)
Step 10: Final decision with confidence % and human-readable reasons block

**Why:** Forcing WAIT when market_quality_row is None is required — proceeding to directional decisions without Polymarket data contradicts the Polymarket-first philosophy.

## DB migration
market_behaviour migration adds: `ALTER TABLE market_quality_scores ADD COLUMN IF NOT EXISTS market_behaviours TEXT NULL`
Stored as comma-joined string e.g. "Increasing Liquidity, Healthy Spread, Buy Pressure".

## What was NOT changed
- No new engines created
- No dashboard/UI/frontend changes
- No API endpoint signature changes
- Existing market_score numeric field preserved for confidence gating
