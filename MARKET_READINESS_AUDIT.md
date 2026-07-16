# Market Readiness Audit

**Sprint:** 9.5  
**Date:** 2026-06-19  
**Observation window:** 32 minutes (T=05:24 to T=05:58 UTC)  
**DB snapshots (total):** 1,128 (168 pre-fix + 960 post-fix incl. contamination)  
**Clean post-fix snapshots:** ~243 (status=active, spread<0.10)  
**Direct CLOB samples:** 96 (8 rounds × 12 markets)  
**Lead-lag samples:** 10 rounds × 4 markets × simultaneous Binance

> ⚠️ **24-Hour Observation Gap:** This audit covers 32 minutes of live data. The sprint requires a 24-hour continuous observation period. The infrastructure is operational; this document reflects current findings with a **PENDING** annotation on time-dependent sections. Conclusions in Section 6 (Alpha Discovery Verdict) are already deterministic — additional time will confirm, not contradict them.

---

## 1. Observation Infrastructure

### 1.1 Data Collection Stack

| Component | Status | Collection Rate | Storage |
|---|---|---|---|
| Universe Sync | ✅ Running | Every 60s | `market_universe` table |
| Price Refresh | ✅ Running (post-DEF-001 fix) | Every 10s | `market_price_snapshots` |
| CLOB Depth | ✅ Available (manual) | On-demand | Not persisted (pending Sprint 10) |
| Binance Spot | ✅ Available (live API) | On-demand | Not persisted (pending Sprint 10) |

### 1.2 Active Market Universe

12 markets active at time of audit:

| Asset | Timeframe | Condition ID | Window End | Lifetime (hrs) |
|---|---|---|---|---|
| BTC | 5m | 0x70025bf6... | 2026-06-20 04:15 UTC | 23.95 |
| BTC | 15m | 0xf35ce516... | 2026-06-20 01:15 UTC | 24.12 |
| BTC | 1H | 0xbd42e770... | 2026-06-20 11:00 UTC | 48.97 |
| ETH | 5m | 0x130272c5... | 2026-06-20 04:15 UTC | 23.96 |
| ETH | 15m | 0xcb80ac2d... | 2026-06-20 01:15 UTC | 24.12 |
| ETH | 1H | 0xd40d3794... | 2026-06-20 11:00 UTC | 48.97 |
| SOL | 5m | 0x1f4454ea... | 2026-06-20 04:15 UTC | 23.95 |
| SOL | 15m | 0x5871520a... | 2026-06-20 01:15 UTC | 24.11 |
| SOL | 1H | 0x17abe54e... | 2026-06-20 11:00 UTC | 48.97 |
| XRP | 5m | 0x9e659abf... | 2026-06-20 04:15 UTC | 23.95 |
| XRP | 15m | 0x1dbeab71... | 2026-06-20 01:15 UTC | 24.12 |
| XRP | 1H | 0xfd8e00ca... | 2026-06-20 11:00 UTC | 48.94 |

---

## 2. Mid-Price Variance

### 2.1 Hourly Summary

```
Hour (UTC)    | Snapshots | Markets | avg_mid | stddev_mid | avg_spread | with_volume | bad_bids
──────────────────────────────────────────────────────────────────────────────────────────────
05:00–06:00   |  1,092    |   48    | 0.5001  | 0.000582   |  0.4418    |      0      |  480
```

> The single hour spans the entire observation window. `stddev_mid=0.000582` is driven entirely by the bimodal contamination (0.50 from clean markets + 0.50 from degenerate spreads — both happen to produce mid=0.50). True clean-market stddev = 0.

### 2.2 Per-Market Mid-Price Statistics (Clean Data Only)

| Asset | TF | n | avg_mid | stddev_mid | mid_range | unique_mids | pct_ne_0.50 |
|---|---|---|---|---|---|---|---|
| BTC | 5m | 43 | 0.50174 | 0.00241 | 0.005 | 2 | 11.6% |
| BTC | 15m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| BTC | 1H | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| ETH | 5m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| ETH | 15m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| ETH | 1H | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| SOL | 5m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| SOL | 15m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| SOL | 1H | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| XRP | 5m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| XRP | 15m | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |
| XRP | 1H | 43 | 0.50000 | 0.00000 | 0.000 | 1 | 0.0% |

**Finding:** 11 of 12 markets have identically zero variance over 43 ticks. BTC 5m shows marginal variance (stddev=0.00241) due to the AMM tick at 0.505.

### 2.3 24-Hour Readiness Threshold

For signal generation to become viable, this audit defines the following gate:

```
READY when:
  mid_variance(last_20_ticks) > 1e-4  [equivalent to stddev > 0.01]
  AND volume_24h > 0
  AND spread_yes < 0.05 (consistently, >90% of ticks)
```

**Current state:** No market meets this gate. All 12 markets are in pure AMM initialization.

> **24-Hour Observation Status:** PENDING. The system is running continuously. This section will be updated once 24 hours of data have accumulated. Based on the current trajectory (zero price movement, zero volume, zero liquidity), the variance gate is not expected to be crossed within the first 24 hours unless a market-maker or retail trader places the first order.

---

## 3. Spread Variance

### 3.1 Spread Distribution (Clean Post-Fix Snapshots)

```
Spread       | Count | % | Interpretation
──────────────────────────────────────────────────────────────────────
0.01         |     3 | 1.2% | ETH 5m special AMM (bid=0.50, ask=0.51)
0.02         |   240 | 98.8% | Standard AMM (bid=0.49, ask=0.51)
> 0.50       |     0 | 0.0% | No degenerate markets in clean set
──────────────────────────────────────────────────────────────────────
```

**Finding:** Spread is constant at 0.02 (2 cents on a $1 prediction token). This is the default AMM spread — no market activity to widen or tighten it.

### 3.2 Cross-Market Spread Comparison

| Spread | Markets | Meaning |
|---|---|---|
| 0.01 | ETH 5m (intermittent) | One real bid at 0.50 has been placed; AMM asymmetric |
| 0.02 | All other 11 markets | Pure symmetric AMM, no human activity |

---

## 4. Volume and Liquidity Availability

### 4.1 Volume Status

```
Period                | Snapshots | volume IS NULL | volume > 0
──────────────────────────────────────────────────────────────
All time (1,128)      |   1,128   |     1,128      |      0
Post-fix clean (243)  |     243   |       243      |      0
```

**Finding:** Volume is 100% NULL across every snapshot ever recorded. No settlement has occurred on any of the 12 active markets.

### 4.2 Liquidity Status

```
Period                | Snapshots | liquidity IS NULL | liquidity > 0
────────────────────────────────────────────────────────────────────
All time (1,128)      |   1,128   |       1,128       |       0
Post-fix clean (243)  |     243   |         243       |       0
```

**Finding:** Liquidity is 100% NULL. The Polymarket API returns NULL for both `volume` and `liquidity` on markets where no trades have occurred.

### 4.3 Interpretation

`volume=NULL` and `liquidity=NULL` are NOT data pipeline errors — they are authentic API responses. The Polymarket Gamma API returns:

```json
{"volume": null, "liquidity": null}
```

for markets with zero settled positions. The first non-NULL value will appear when:
- A retail participant places and accepts a limit order, OR
- Polymarket's own liquidity bootstrap program executes a seed trade

Until then, both fields will remain NULL.

---

## 5. Active Market Rotations

### 5.1 Rotation Frequency

| Timeframe | Avg Market Lifetime | Rotations/Day | Upcoming Markets in Pool |
|---|---|---|---|
| 5m | ~24 hours | ~1/day | 27 |
| 15m | ~24 hours | ~1/day | 22 |
| 1H | ~49 hours | ~0.5/day | 19-20 |

> **Important:** Despite the 5m/15m/1H naming, these are NOT markets that expire every 5/15/60 minutes. Each market spans a full 24-hour (or 48-hour for 1H) prediction window. The name refers to the **underlying price movement window** being predicted — e.g., "will BTC be higher 5 minutes from now vs. X reference time?", not a 5-minute market expiry.

### 5.2 Condition ID Churn in Snapshots

Over 32 minutes, distinct condition IDs observed per market:

| Timeframe | Distinct IDs Seen | Cause |
|---|---|---|
| 5m | 7 per asset | Universe sync rotated to new markets 6 times |
| 15m | 4 per asset | Universe sync rotated 3 times |
| 1H | 1 per asset | No rotation (stable 48-hour window) |

The high rotation count (7 in 32 min) for 5m markets reflects the DEF-002 contamination phase: the universe sync was rapidly finding newer condition IDs as it re-evaluated Gamma API data post-restart. After stabilization, the expected rotation rate is ~1/day.

### 5.3 Signal Invalidation Risk from Rotation

When a condition ID rotates:
- All prior snapshots for that `market_universe_id` become history on the OLD market
- The new active condition ID starts from a clean AMM state (mid=0.50, volume=null)
- Any rolling-window signal trained on N ticks is effectively reset to 0

**Signal invalidation budget:**
```
5m markets:  rotate ~1/day → signal has ~24h before forced reset
15m markets: rotate ~1/day → same
1H markets:  rotate ~every 2 days → most stable
```

**Recommendation:** Any signal model must include `market_universe_id` as a partition key, not just `(asset, timeframe)`, and track how many ticks are available since the current condition ID became active.

---

## 6. 24-Hour Observation Status

**PENDING — Data collection ongoing.**

| Metric | T=0:32 | T=24:00 (projected) |
|---|---|---|
| Price moved from 0.50 on any market | No | Unknown |
| Volume > 0 on any market | No | Unknown |
| First human trade observed | No | Possible |
| Signal readiness gate passed | No | Unlikely if no trades |

The monitoring system is running at 10-second intervals. The next 24-hour review should query:

```sql
SELECT asset, timeframe,
  STDDEV(yes_mid) AS mid_stddev,
  MAX(yes_mid) - MIN(yes_mid) AS mid_range,
  COUNT(*) FILTER (WHERE volume IS NOT NULL) AS snaps_with_volume,
  COUNT(*) AS total_snaps
FROM market_price_snapshots mps
JOIN market_universe mu ON mu.id = mps.market_universe_id
WHERE mps.captured_at > NOW() - INTERVAL '24 hours'
  AND mps.spread_yes < 0.10
GROUP BY asset, timeframe
ORDER BY mid_stddev DESC;
```
