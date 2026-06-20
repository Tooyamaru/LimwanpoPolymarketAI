# Audit #5 — Part C: Live 30-Minute Market Observation
**Date:** 2026-06-20 | **Markets:** BTC/ETH/SOL/XRP × 1H  
**Method:** 180 rounds × 10s interval = 30 minutes continuous live observation  
**Status:** COLLECTION IN PROGRESS — partial results below, final results appended when complete

---

## 1. Observation Design

| Parameter | Value |
|-----------|-------|
| Markets | BTC/1H, ETH/1H, SOL/1H, XRP/1H |
| Data source | `GET https://clob.polymarket.com/book?token_id=...` |
| Round interval | 10 seconds |
| Total rounds | 180 |
| Duration | 30 minutes |
| Spot reference | Binance BTCUSDT/ETHUSDT/SOLUSDT/XRPUSDT via REST |
| Fields per round | best_bid, best_ask, mid, spread, bid_levels, ask_levels, top5_bid, top5_ask, imbalance |
| Change tracking | mid_chg, bid_chg, ask_chg, depth_chg, any_chg flags vs. previous round |

Context: This collection runs on the currently-live 1H markets that have already been observed for 360 rounds (~1 hour) in the Audit #4 dataset. Part C therefore extends total continuous observation to ~2.5 hours.

---

## 2. Preliminary Results (Round 30 of 180)

At round 30 (~5 minutes elapsed):

| Metric | Value |
|--------|-------|
| Unique mid prices observed | {0.5} — one value only |
| Mid-price changes | **0** |
| Any-change events | **0** |
| Markets responsive | 4/4 (all returning valid book data) |
| BTC spot (round 30) | ~$63,684 |

Observation consistent with all prior audit results. Books are completely frozen.

---

## 3. Full Results

*(This section will be populated with final analysis data once collection completes at round 180.)*

### 3a. Mid-Price Stability
- Round range with no mid change: **[0, N]** — TBD
- Total mid changes across 4 markets × 180 rounds: **TBD**
- Variance of mid prices: **TBD**

### 3b. Depth Changes
- Top5 depth change events: **TBD**
- Bid-level count changes: **TBD**

### 3c. Spot–CLOB Correlation
- BTC/1H mid vs. BTC spot correlation: **TBD**
- ETH/1H mid vs. ETH spot correlation: **TBD**

### 3d. Imbalance Dynamics
- Imbalance range observed: **TBD**

---

## 4. Comparison to Audit #4 Baseline

| Metric | Audit #4 (360 rounds) | Part C (180 rounds, preliminary) |
|--------|----------------------|----------------------------------|
| Mid changes | 0 | 0 (first 30 rounds) |
| Depth changes | 1 (at round 300) | 0 (no round-300 equivalent yet) |
| BTC spot range | $62,350–$63,698 | TBD |
| CLOB–Spot correlation | r = −0.022 | TBD |

---

*[Final results appended below after collection completes at approximately 06:52 UTC]*
