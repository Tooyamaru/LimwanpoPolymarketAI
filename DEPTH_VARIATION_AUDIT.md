# DEPTH_VARIATION_AUDIT.md

**Collection started:** 2026-06-19 07:21:49 UTC
**Collection ended:**   2026-06-19 07:41:52 UTC
**Observation span:**   20.0 minutes (1203 s)
**Sampling interval:**  10 s
**Rounds completed:**   121
**Valid snapshots:**    1452 (0 failed)
**Markets audited:**    12

---

## 1. Methodology

**Source:** `GET https://clob.polymarket.com/book?token_id={yes_token_id}`  
**Sampling:** One YES-token order book snapshot per market per round.  
**Book convention:** bids sorted ascending (best bid = last element); asks sorted descending (best ask = last element).  

**Metric definitions:**

| Metric | Formula |
|---|---|
| `depth_imbalance_top5` | `(Σbid_size_top5 − Σask_size_top5) / (Σbid_size_top5 + Σask_size_top5)` — range [−1, +1] |
| `depth_imbalance_top10` | Same using top-10 levels |
| `total_bid_size` | Sum of all resting bid sizes (USDC notional) |
| `total_ask_size` | Sum of all resting ask sizes (USDC notional) |
| `bid_pressure_pct` | `total_bid / (total_bid + total_ask) × 100` |
| `number_of_bid_levels` | Count of distinct bid price levels |
| `number_of_ask_levels` | Count of distinct ask price levels |

**Variation threshold:** CV% > 1.0% classified as meaningful.  
**Classification rule:**
- `DEPTH STATIC`: all metric CV% ≤ 1.0%
- `DEPTH CHANGING WITH STRUCTURE`: size CV% > 1.0% AND imbalance CV% > 1.0% (directional shift)
- `DEPTH CHANGING BUT RANDOM`: size varies but imbalance does not (symmetric noise)

---

## 2. Per-Market Results

### BTC/5m  (n=121, mid price range: 0.5050 – 0.5050)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | -0.0790 | -0.0790 | -0.0790 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | -0.0840 | -0.0840 | -0.0840 | 0.0000 | 0.00% |
| `total_bid_size` | 47297.4000 | 47297.4000 | 47297.4000 | 0.0000 | 0.00% |
| `total_ask_size` | 46971.6400 | 46971.6400 | 46971.6400 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.1728 | 50.1728 | 50.1728 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 48.0000 | 48.0000 | 48.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 47.0000 | 47.0000 | 47.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### BTC/15m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0035 | 0.0035 | 0.0035 | 0.0000 | 0.00% |
| `total_bid_size` | 43268.5700 | 43268.5700 | 43268.5700 | 0.0000 | 0.00% |
| `total_ask_size` | 43181.5700 | 43181.5700 | 43181.5700 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.0503 | 50.0503 | 50.0503 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 46.0000 | 46.0000 | 46.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 46.0000 | 46.0000 | 46.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### BTC/1H  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 26870.3500 | 26870.3500 | 26870.3500 | 0.0000 | 0.00% |
| `total_ask_size` | 26870.3500 | 26870.3500 | 26870.3500 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 24.0000 | 24.0000 | 24.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 24.0000 | 24.0000 | 24.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### ETH/5m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 31764.4700 | 31769.6200 | 31766.6832 | 2.5601 | 0.01% |
| `total_ask_size` | 31764.4700 | 31769.6200 | 31766.6832 | 2.5601 | 0.01% |
| `bid_pressure_pct` | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### ETH/15m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0048 | 0.0048 | 0.0048 | 0.0000 | 0.00% |
| `total_bid_size` | 34004.1900 | 34004.1900 | 34004.1900 | 0.0000 | 0.00% |
| `total_ask_size` | 33925.1900 | 33925.1900 | 33925.1900 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.0581 | 50.0581 | 50.0581 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 35.0000 | 35.0000 | 35.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 35.0000 | 35.0000 | 35.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### ETH/1H  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 23823.3600 | 23823.3600 | 23823.3600 | 0.0000 | 0.00% |
| `total_ask_size` | 23823.4000 | 23823.4000 | 23823.4000 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 34.0000 | 34.0000 | 34.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 34.0000 | 34.0000 | 34.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### SOL/5m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 18869.0500 | 18869.0500 | 18869.0500 | 0.0000 | 0.00% |
| `total_ask_size` | 18819.0500 | 18819.0500 | 18819.0500 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.0663 | 50.0663 | 50.0663 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 44.0000 | 44.0000 | 44.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 44.0000 | 44.0000 | 44.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### SOL/15m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 13157.7500 | 13157.7500 | 13157.7500 | 0.0000 | 0.00% |
| `total_ask_size` | 13185.7500 | 13185.7500 | 13185.7500 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 49.9469 | 49.9469 | 49.9469 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 43.0000 | 43.0000 | 43.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 43.0000 | 43.0000 | 43.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### SOL/1H  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 6484.3800 | 6484.3800 | 6484.3800 | 0.0000 | 0.00% |
| `total_ask_size` | 6494.3800 | 6494.3800 | 6494.3800 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 49.9615 | 49.9615 | 49.9615 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 31.0000 | 31.0000 | 31.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 31.0000 | 31.0000 | 31.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### XRP/5m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 19631.6700 | 19631.6700 | 19631.6700 | 0.0000 | 0.00% |
| `total_ask_size` | 19431.6700 | 19431.6700 | 19431.6700 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 50.2560 | 50.2560 | 50.2560 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 42.0000 | 42.0000 | 42.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 42.0000 | 42.0000 | 42.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### XRP/15m  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 11004.9300 | 11004.9300 | 11004.9300 | 0.0000 | 0.00% |
| `total_ask_size` | 11056.9300 | 11056.9300 | 11056.9300 | 0.0000 | 0.00% |
| `bid_pressure_pct` | 49.8821 | 49.8821 | 49.8821 | 0.0000 | 0.00% |
| `number_of_bid_levels` | 37.0000 | 37.0000 | 37.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 38.0000 | 38.0000 | 38.0000 | 0.0000 | 0.00% |

**→ DEPTH STATIC**

### XRP/1H  (n=121, mid price range: 0.5000 – 0.5000)

| Metric | Min | Max | Mean | Std Dev | CV% |
|---|---|---|---|---|---|
| `depth_imbalance_top5` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `depth_imbalance_top10` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% |
| `total_bid_size` | 5586.1100 | 5650.1100 | 5632.1238 | 27.8282 | 0.49% |
| `total_ask_size` | 5524.7600 | 5665.7600 | 5634.5146 | 33.5406 | 0.60% |
| `bid_pressure_pct` | 49.9301 | 50.5609 | 49.9895 | 0.0639 | 0.13% |
| `number_of_bid_levels` | 19.0000 | 19.0000 | 19.0000 | 0.0000 | 0.00% |
| `number_of_ask_levels` | 18.0000 | 19.0000 | 18.9917 | 0.0909 | 0.48% |

**→ DEPTH STATIC**

---

## 3. Cross-Market Comparison

### 3.1  CV% distribution by metric (all 12 markets)

| Metric | Min CV% | Max CV% | Mean CV% | Markets with CV% > 1.0 |
|---|---|---|---|---|
| `depth_imbalance_top5` | 0.00% | 0.00% | 0.00% | 0/12 |
| `depth_imbalance_top10` | 0.00% | 0.00% | 0.00% | 0/12 |
| `total_bid_size` | 0.00% | 0.49% | 0.04% | 0/12 |
| `total_ask_size` | 0.00% | 0.60% | 0.05% | 0/12 |
| `bid_pressure_pct` | 0.00% | 0.13% | 0.01% | 0/12 |
| `number_of_bid_levels` | 0.00% | 0.00% | 0.00% | 0/12 |
| `number_of_ask_levels` | 0.00% | 0.48% | 0.04% | 0/12 |

### 3.2  Per-market classification summary

| Market | Max CV% | Best-bid mean | Total-bid mean | Classification |
|---|---|---|---|---|
| BTC/5m | 0.00% | 0.5000 | 47297 | DEPTH STATIC |
| BTC/15m | 0.00% | 0.4900 | 43269 | DEPTH STATIC |
| BTC/1H | 0.00% | 0.4900 | 26870 | DEPTH STATIC |
| ETH/5m | 0.01% | 0.4900 | 31767 | DEPTH STATIC |
| ETH/15m | 0.00% | 0.4900 | 34004 | DEPTH STATIC |
| ETH/1H | 0.00% | 0.4900 | 23823 | DEPTH STATIC |
| SOL/5m | 0.00% | 0.4900 | 18869 | DEPTH STATIC |
| SOL/15m | 0.00% | 0.4900 | 13158 | DEPTH STATIC |
| SOL/1H | 0.00% | 0.4900 | 6484 | DEPTH STATIC |
| XRP/5m | 0.00% | 0.4900 | 19632 | DEPTH STATIC |
| XRP/15m | 0.00% | 0.4900 | 11005 | DEPTH STATIC |
| XRP/1H | 0.60% | 0.4900 | 5632 | DEPTH STATIC |

### 3.3  Statistical distinctness (total bid size)

Global mean total bid size: 23484 USDC  |  Std dev across markets: 13670 USDC

| Market | Mean bid size | Z-score | Statistically distinct? |
|---|---|---|---|
| BTC/15m | 43269 | +1.45 | no |
| BTC/1H | 26870 | +0.25 | no |
| BTC/5m | 47297 | +1.74 | no |
| ETH/15m | 34004 | +0.77 | no |
| ETH/1H | 23823 | +0.02 | no |
| ETH/5m | 31767 | +0.61 | no |
| SOL/15m | 13158 | -0.76 | no |
| SOL/1H | 6484 | -1.24 | no |
| SOL/5m | 18869 | -0.34 | no |
| XRP/15m | 11005 | -0.91 | no |
| XRP/1H | 5632 | -1.31 | no |
| XRP/5m | 19632 | -0.28 | no |

---

## 4. Temporal Structure Analysis

First-half vs second-half mean comparison (total_bid_size) — detects slow drift:

| Market | First-half mean | Second-half mean | Δ% | Drift present? |
|---|---|---|---|---|
| BTC/5m | 47297 | 47297 | +0.00% | no |
| BTC/15m | 43269 | 43269 | +0.00% | no |
| BTC/1H | 26870 | 26870 | +0.00% | no |
| ETH/5m | 31764 | 31769 | +0.01% | no |
| ETH/15m | 34004 | 34004 | +0.00% | no |
| ETH/1H | 23823 | 23823 | +0.00% | no |
| SOL/5m | 18869 | 18869 | +0.00% | no |
| SOL/15m | 13158 | 13158 | +0.00% | no |
| SOL/1H | 6484 | 6484 | +0.00% | no |
| XRP/5m | 19632 | 19632 | +0.00% | no |
| XRP/15m | 11005 | 11005 | +0.00% | no |
| XRP/1H | 5650 | 5614 | -0.63% | no |

Imbalance (top-5) range across rounds — detects directional pressure:

| Market | Min imbalance | Max imbalance | Range | Any non-zero? |
|---|---|---|---|---|
| BTC/5m | -0.079024 | -0.079024 | 0.000000 | YES |
| BTC/15m | +0.000000 | +0.000000 | 0.000000 | no |
| BTC/1H | +0.000000 | +0.000000 | 0.000000 | no |
| ETH/5m | +0.000000 | +0.000000 | 0.000000 | no |
| ETH/15m | +0.000000 | +0.000000 | 0.000000 | no |
| ETH/1H | +0.000000 | +0.000000 | 0.000000 | no |
| SOL/5m | +0.000000 | +0.000000 | 0.000000 | no |
| SOL/15m | +0.000000 | +0.000000 | 0.000000 | no |
| SOL/1H | +0.000000 | +0.000000 | 0.000000 | no |
| XRP/5m | +0.000000 | +0.000000 | 0.000000 | no |
| XRP/15m | +0.000000 | +0.000000 | 0.000000 | no |
| XRP/1H | +0.000000 | +0.000000 | 0.000000 | no |

---

## 5. Conclusion

### Overall: DEPTH STATIC

- **DEPTH STATIC:** 12/12 markets

**All-metric CV% range across all markets:** 0.0000% – 0.5953%
**All-metric mean CV%:** 0.0204%

**Evidence:**

- Total bid/ask size CV%: mean 0.0461%, max 0.5953%  
  → Book size is stable. Neither side adds or removes liquidity meaningfully over the observation window.
- Depth imbalance CV%: mean 0.0000%, max 0.0000%  
  → No directional pressure detected. Both sides move together if they move at all.
- Level count CV%: mean 0.0199%, max 0.4787%  
  → Number of resting price levels is constant throughout the observation window.

All seven metrics are statistically stable across all 12 markets for the full observation period.
The order book is structurally inert: depth, imbalance, and level count do not vary in any
market despite the constant mid-price. This is consistent with a fully automated market maker
maintaining a fixed symmetric book with no external order flow.

*All data collected live from the Polymarket CLOB API. No synthetic or cached values used.*