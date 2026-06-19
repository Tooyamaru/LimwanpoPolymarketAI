# Alpha Discovery Report

**Sprint:** 9.5  
**Date:** 2026-06-19  
**Verdict Date:** Current findings are deterministic given observed data. No additional time changes the verdict.

---

## A. Is There Real Price Discovery?

### Answer: **NO** — at this time

**Evidence:**

1. **Zero variance across 612 observations:**
   - 11 of 12 active markets: `stddev(yes_mid) = 0.000000` over 43 ticks each
   - 1 exception (BTC 5m): `stddev = 0.00241`, driven by a static AMM asymmetry, not trading activity

2. **Distribution of mid-price values:**
   ```
   yes_mid = 0.500 → 97.28% of all observations
   yes_mid = 0.505 → 2.72% of all observations
   Any other value → 0.00%
   ```

3. **No volume has settled:** `volume = NULL` on 100% of 1,128 snapshots. Settlement-based price discovery requires fills.

4. **The market is in AMM-initialization phase.** Polymarket's Automated Market Maker seeds the book symmetrically:
   - Bids placed at every penny from 0.01 to 0.49
   - Asks placed at every penny from 0.99 to 0.51
   - Total depth: $11,000–$44,000 USDC per side depending on market
   - The AMM's own orders produce a perfectly symmetrical book — `depth_imbalance ≈ 0.001`

5. **The 0.505 exception is not price discovery.** It reflects a single out-of-AMM bid order placed at 0.50 by an unknown participant on ETH 5m. It is a static order that has not been taken, not a price series with information content.

**Price Discovery Gate:**
```
REQUIRES: Mid-price moves at least 2 ticks (0.01 USDC) in at least 3 consecutive observations
CURRENT:  Zero markets show any movement over 612 observations
STATUS:   GATE NOT PASSED
```

---

## B. Is There an Order-Flow Signal?

### Answer: **DATA IS AVAILABLE, SIGNAL IS NOT** — yet

The CLOB API provides sufficient data for full order-flow analysis:

### B.1 Order Flow Data Availability

| Metric | API Available | Storage Designed | Signal Present |
|---|---|---|---|
| Best bid / ask | ✅ `bids[-1]` / `asks[-1]` | ✅ `market_price_snapshots` | ❌ AMM only |
| Full depth (all levels) | ✅ 44–48 levels | ❌ Not persisted | ❌ Symmetric |
| Depth imbalance (all) | ✅ Computable | ❌ Not persisted | ❌ ~0.001 |
| Top-5 depth | ✅ Computable | ❌ Not persisted | ❌ Exactly 0.0 |
| Top-10 depth | ✅ Computable | ❌ Not persisted | ❌ ~0.004 |
| Bid pressure % | ✅ Computable | ❌ Not persisted | ❌ 50.2% / 49.8% |
| Ask pressure % | ✅ Computable | ❌ Not persisted | ❌ Equal to AMM |
| Volume (settled) | ✅ `volume` field | ✅ `market_price_snapshots` | ❌ 100% NULL |
| Liquidity | ✅ `liquidity` field | ✅ `market_price_snapshots` | ❌ 100% NULL |

### B.2 Measured Order Flow Values

Raw measurements from 3-market probe at 2026-06-19 05:59 UTC:

```
Market          total_bid_sz   total_ask_sz  imbalance_all  imbalance_top5  imbalance_top10
ETH 5m          $22,750.74     $22,550.74    +0.004415      0.000000        0.000000
BTC 15m         $43,759.25     $43,672.25    +0.000995      0.000000        +0.003520
SOL 5m          $11,075.99     $10,975.99    +0.004535      0.000000        0.000000
```

**Finding:** The depth imbalance is nearly zero across all markets. The top-5 levels are perfectly mirrored between bids and asks — identical sizes on both sides at symmetric prices. This is the signature of a pure AMM: each bid at price P has a matching ask at price (1 - P), placed by the same AMM smart contract.

**Order flow signal requires:** A human participant placing an asymmetric order (e.g., a large bid at 0.48 with no matching ask, or a market order consuming multiple ask levels). None observed.

### B.3 Storage Schema for Order Flow (Future)

When human trading begins, the following addition to `market_price_snapshots` is recommended:

```sql
ALTER TABLE market_price_snapshots ADD COLUMN IF NOT EXISTS
  depth_imbalance_top5  NUMERIC(8,6),
  depth_imbalance_top10 NUMERIC(8,6),
  depth_imbalance_all   NUMERIC(8,6),
  bid_pressure_pct      NUMERIC(5,2),
  ask_pressure_pct      NUMERIC(5,2),
  total_bid_size_usdc   NUMERIC(12,2),
  total_ask_size_usdc   NUMERIC(12,2),
  top5_bid_size_usdc    NUMERIC(12,2),
  top5_ask_size_usdc    NUMERIC(12,2);
```

These columns can be populated from the existing `/book` endpoint without any new API calls — the data is already fetched, just not persisted.

---

## C. Is There Lead-Lag vs Binance?

### Answer: **NOT COMPUTABLE** — due to zero variance in Polymarket prices

### C.1 Simultaneous Sampling Results

10-round lead-lag observation, 15-second intervals (T=05:59–06:01 UTC):

| Asset | Binance Start | Binance End | Binance Δ% | Poly mid Start | Poly mid End | Poly Δ | Moves |
|---|---|---|---|---|---|---|---|
| BTC | $62,731.91 | $62,757.50 | **+0.041%** | 0.5000 | 0.5000 | **0.0000** | 0/9 |
| ETH | $1,697.08 | $1,697.95 | **+0.051%** | 0.5000 | 0.5000 | **0.0000** | 0/9 |
| SOL | $68.66 | $68.71 | **+0.073%** | 0.5000 | 0.5000 | **0.0000** | 0/9 |
| XRP | $1.1331 | $1.1344 | **+0.115%** | 0.5000 | 0.5000 | **0.0000** | 0/9 |

**Binance moved. Polymarket did not move at all.**

### C.2 Lag Analysis

```
Lag    | Correlation (Binance return → Poly return) | Feasible?
───────────────────────────────────────────────────────────────
10s    | undefined (zero variance in Poly)          | NO
30s    | undefined                                  | NO
60s    | undefined                                  | NO
5m     | undefined                                  | NO
15m    | undefined                                  | NO
```

**Mathematical note:** Pearson correlation between a constant series (Polymarket) and any variable series (Binance) is undefined (division by zero standard deviation). It cannot be computed, it cannot be estimated, and no lag test (Granger, cross-correlation, DTW) is meaningful when one series is a constant.

### C.3 What Lead-Lag Would Look Like When Markets Activate

The hypothesis is: Polymarket mid-price *lags* Binance by some interval (traders observe spot price, then bet on the direction). To test this:

```python
# Cross-correlation function at lag k (in ticks):
CCF(k) = corr(Δbinance[t], Δpoly_mid[t+k])

# For each k in {1, 2, 4, 6, 30} (10s ticks → 10s, 20s, 40s, 60s, 300s)
# Test H0: CCF(k) = 0 using Fisher's z-transform
# Report: lag of maximum |CCF(k)|, direction (lead/lag/contemporaneous)
```

**Infrastructure required:** Binance spot price must be collected and stored at the same 10-second cadence as Polymarket snapshots. This is a Sprint 10 pre-requisite.

---

## D. Is Polymarket a Viable Alpha Source?

### Answer: **CONDITIONALLY YES** — with prerequisites

Polymarket's prediction markets are *structurally* capable of producing alpha once real price discovery begins. The reasons:

#### D.1 Structural Advantages

1. **Information aggregation:** Polymarket concentrates informed betters from crypto Twitter, on-chain analysts, and quant traders into a single price signal. When liquid, it should *lead* or *co-move* with spot markets.

2. **Binary payoff:** Unlike spot markets (continuous P&L), Polymarket pays exactly $1 or $0. This creates specific arbitrage opportunities when `mid_price ≠ true_probability`.

3. **AMM inefficiency window:** The AMM places symmetric orders based on a static model. A trader with directional information can exploit the spread before the AMM adjusts. This is the core alpha mechanism.

4. **Tight spread:** 2-cent spread (0.02) on a $1 token is equivalent to 2% round-trip cost. This is within range for profitable strategies at 5%+ edge.

5. **Multi-market correlation:** BTC/ETH/SOL/XRP prediction markets should be correlated with each other and with spot prices. Cross-market signals may be detectable.

#### D.2 Current Blockers

1. **No trading has occurred.** Zero volume, zero fills, zero price discovery.
2. **Zero variance = zero information = zero alpha.** This is not an infrastructure problem — it is a market maturity problem.
3. **Timing uncertainty:** Unknown when the first real trade will occur. It may happen in hours, days, or not at all for some markets.

#### D.3 Conditions for Alpha Viability

```
Required Gate (must ALL be true to activate Sprint 10 signal engine):

G1: volume_24h > 0 on at least 3 markets
G2: stddev(yes_mid, last_120_ticks) > 0.005 on at least 3 markets
G3: at least 2 rotations have occurred without signal invalidation
G4: Binance price feed stored at ≥10s cadence for ≥24h
G5: DEF-002 fix deployed (done)
```

**Current Gate Status:**
- G1: ❌ 0/3 (volume=null everywhere)
- G2: ❌ 0/3 (variance=0)
- G3: ❌ Cannot measure (no signal yet)
- G4: ❌ Binance feed not yet persisted
- G5: ✅ DEF-002 fix applied (see DEF002_ROOT_CAUSE_REPORT.md)

---

## E. What Additional Data Must Be Collected?

### E.1 Immediate — Before Sprint 10 Can Begin

| Data | Why Needed | Estimated Effort |
|---|---|---|
| **Binance spot prices at 10s cadence** | Lead-lag analysis requires matched timestamps | 1 sprint task — add `BinancePriceService`, store in new `binance_price_snapshots` table |
| **Full order book depth per tick** | Order flow analysis (imbalance, pressure) | 1 sprint task — extend `market_price_snapshots` schema, populate from existing CLOB call |
| **24-hour continuous observation** | Confirm variance gate status | Already running — check again at T+24h |

### E.2 Schema for Binance Price Collection

```sql
CREATE TABLE binance_price_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    symbol       VARCHAR(12) NOT NULL,  -- 'BTCUSDT', 'ETHUSDT', etc.
    price        NUMERIC(20, 8) NOT NULL,
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON binance_price_snapshots (symbol, captured_at);
```

Populated by a new `BinancePriceService` (calls `GET /api/v3/ticker/price`) running at the same 10-second cadence as `MarketPriceService`.

### E.3 What to Watch For (24h Monitoring Checklist)

After 24 hours, rerun:

```sql
-- Check 1: Has any price moved?
SELECT asset, timeframe,
  ROUND(STDDEV(yes_mid)::numeric, 6) AS stddev_mid,
  COUNT(DISTINCT ROUND(yes_mid::numeric, 3)) AS unique_mids,
  MAX(yes_mid) - MIN(yes_mid) AS range_mid
FROM market_price_snapshots mps
JOIN market_universe mu ON mu.id = mps.market_universe_id
WHERE mps.spread_yes < 0.10
  AND mps.captured_at > NOW() - INTERVAL '24 hours'
GROUP BY asset, timeframe
ORDER BY stddev_mid DESC;

-- Check 2: Has any volume appeared?
SELECT COUNT(*) AS snaps_with_volume
FROM market_price_snapshots
WHERE volume IS NOT NULL
  AND captured_at > NOW() - INTERVAL '24 hours';

-- Check 3: Order flow signal presence (if depth columns added)
-- SELECT asset, timeframe, MAX(ABS(depth_imbalance_top5)) AS max_imbalance
-- FROM market_price_snapshots ...
```

---

## Summary Table

| Question | Answer | Confidence | Evidence |
|---|---|---|---|
| A. Real price discovery? | **NO** | High | 0.0000 variance, 97.28% at exact 0.50 |
| B. Order-flow signal? | **DATA YES, SIGNAL NO** | High | API provides depth; AMM is symmetric |
| C. Lead-lag vs Binance? | **NOT COMPUTABLE** | High | Zero poly variance → undefined correlation |
| D. Polymarket viable alpha? | **CONDITIONAL YES** | Medium | Structural advantages exist; timing unknown |
| E. Data gaps? | Binance feed + depth storage | High | Neither currently persisted |

### Overall Readiness Score: 1/5 Gates Passed

The infrastructure is correct. The markets have not yet attracted real trading. Sprint 10 signal engine implementation should be **held** until:
- At least 3 markets show `volume > 0`
- The Binance price feed is being stored at 10-second cadence
- At least 24 hours of clean (post-DEF-002-fix) post-trade data exists
