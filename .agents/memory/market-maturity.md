---
name: Market maturity status
description: All 12 active Polymarket prediction markets are in AMM initialization phase as of 2026-06-19; no human trading has occurred
---

As of 2026-06-19 (Sprint 9.5 observation window):
- All 12 active markets (4 assets × 3 timeframes) show `yes_mid = 0.500` constantly
- `stddev(yes_mid) = 0` on 11/12 markets over 612 observations
- `volume = NULL`, `liquidity = NULL` on 100% of 1,128+ snapshots
- The markets are in **pure AMM initialization phase** — Polymarket's AMM places symmetric orders (bid=0.49, ask=0.51, depth=44-48 levels per side), no human orders have been placed
- `depth_imbalance ≈ 0.001` (perfectly symmetric)

**Signal feasibility verdict: NO** until at least 3 markets show `volume > 0` and `stddev(yes_mid, last 120 ticks) > 0.005`.

**Why this matters:** Sprint 10 signal engine cannot be built on this data — any signal would output 50% by construction (constant target variable). Sprint 10 is gated on the readiness conditions in `ALPHA_DISCOVERY_REPORT.md`.

**How to apply:** Before starting Sprint 10 signal work, run the readiness gate SQL from `MARKET_READINESS_AUDIT.md` Section 6.
