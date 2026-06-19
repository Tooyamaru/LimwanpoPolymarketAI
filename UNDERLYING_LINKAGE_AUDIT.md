# UNDERLYING_LINKAGE_AUDIT.md

**Collection started:** 2026-06-19T09:38:15.243464+00:00
**Collection ended:**   2026-06-19T09:55:56.663876+00:00  *(in progress)*
**Observation span:**   17.5 minutes (1051 s)
**Sampling interval:**  10 s
**Rounds completed:**   99 / 360
**Valid CLOB snapshots:** 1188
**Valid spot samples:**   396

---

## 1. Methodology

**CLOB source:** `GET https://clob.polymarket.com/book?token_id=…`  
**Spot source:**  `GET https://api.binance.com/api/v3/ticker/price`  
**Asset return:** `(price_t − price_{t−1}) / price_{t−1}` per 10-second interval  
**AMM mid change:** `mid_t − mid_{t−1}` (exact price delta)  
**Depth change flag:** 1 if `top5_bid_depth` or `top5_ask_depth` changed, else 0  
**Correlation:** Pearson r (returns None when a variable has zero variance)  
**Lag k:** correlate spot return at round t with AMM metric at round t+k  
  (k=+1 means 'does AMM react 10s after spot moves?')  

---

## 2. Spot Price Summary

| Asset | Min | Max | Range% | Samples | Non-zero returns |
|---|---|---|---|---|---|
| BTC | 62350.3200 | 62465.9600 | 0.1855% | 99 | 89 |
| ETH | 1688.7300 | 1694.0000 | 0.3121% | 99 | 83 |
| SOL | 68.3100 | 68.5000 | 0.2781% | 99 | 77 |
| XRP | 1.1247 | 1.1271 | 0.2134% | 99 | 72 |

## 3. AMM Market Summary

| Market | Mid unique vals | Mid changes | Depth changes | Best bid | Best ask | Spread |
|---|---|---|---|---|---|---|
| BTC/5m | [0.505] | 0 | 0 | 0.5000 | 0.5100 | 0.01 |
| BTC/15m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| BTC/1H | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| ETH/5m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| ETH/15m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| ETH/1H | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| SOL/5m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| SOL/15m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| SOL/1H | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| XRP/5m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| XRP/15m | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |
| XRP/1H | [0.5] | 0 | 0 | 0.4900 | 0.5100 | 0.02 |

## 4. Correlation Analysis

### 4.1 Contemporaneous: spot return at t vs AMM mid change at t

*(Pearson r — None = zero variance in one series, correlation undefined)*

| Market | Asset | r(spot_ret, mid_delta) | r(spot_ret, depth_chg) |
|---|---|---|---|
| BTC/5m | BTC | None | None |
| BTC/15m | BTC | None | None |
| BTC/1H | BTC | None | None |
| ETH/5m | ETH | None | None |
| ETH/15m | ETH | None | None |
| ETH/1H | ETH | None | None |
| SOL/5m | SOL | None | None |
| SOL/15m | SOL | None | None |
| SOL/1H | SOL | None | None |
| XRP/5m | XRP | None | None |
| XRP/15m | XRP | None | None |
| XRP/1H | XRP | None | None |

### 4.2 Lagged: spot return at t vs AMM metric at t+k (does AMM react after spot moves?)

| Market | Asset | k=+1 (10s) | k=+2 (20s) | k=+3 (30s) | k=+6 (60s) | k=+12 (120s) |
|---|---|---|---|---|---|---|
| BTC/5m | BTC | None | None | None | None | None |
| BTC/15m | BTC | None | None | None | None | None |
| BTC/1H | BTC | None | None | None | None | None |
| ETH/5m | ETH | None | None | None | None | None |
| ETH/15m | ETH | None | None | None | None | None |
| ETH/1H | ETH | None | None | None | None | None |
| SOL/5m | SOL | None | None | None | None | None |
| SOL/15m | SOL | None | None | None | None | None |
| SOL/1H | SOL | None | None | None | None | None |
| XRP/5m | XRP | None | None | None | None | None |
| XRP/15m | XRP | None | None | None | None | None |
| XRP/1H | XRP | None | None | None | None | None |

### 4.3 Reverse lag: spot return at t vs AMM metric at t-k (does AMM lead spot?)

| Market | Asset | k=-1 (10s) | k=-2 (20s) | k=-3 (30s) | k=-6 (60s) | k=-12 (120s) |
|---|---|---|---|---|---|---|
| BTC/5m | BTC | None | None | None | None | None |
| BTC/15m | BTC | None | None | None | None | None |
| BTC/1H | BTC | None | None | None | None | None |
| ETH/5m | ETH | None | None | None | None | None |
| ETH/15m | ETH | None | None | None | None | None |
| ETH/1H | ETH | None | None | None | None | None |
| SOL/5m | SOL | None | None | None | None | None |
| SOL/15m | SOL | None | None | None | None | None |
| SOL/1H | SOL | None | None | None | None | None |
| XRP/5m | XRP | None | None | None | None | None |
| XRP/15m | XRP | None | None | None | None | None |
| XRP/1H | XRP | None | None | None | None | None |

## 5. AMM Reaction Event Log

Any round where AMM changed AND spot moved >0.01% in the preceding 3 rounds:

*(no AMM changes co-occurred with spot moves >0.01% in the preceding 3 rounds)*

## 6. Spot Volatility During Observation

10-second return statistics:

| Asset | n_returns | mean_ret | std_ret | min_ret | max_ret | non_zero |
|---|---|---|---|---|---|---|
| BTC | 98 | -0.00001245 | 0.00019646 | -0.00073210 | 0.00080044 | 89 |
| ETH | 98 | -0.00002003 | 0.00030565 | -0.00242787 | 0.00066751 | 83 |
| SOL | 98 | -0.00001337 | 0.00034036 | -0.00204529 | 0.00087681 | 77 |
| XRP | 98 | -0.00000631 | 0.00028058 | -0.00159787 | 0.00071048 | 72 |

## 7. Conclusion

**Total AMM reprice events:** 0  
*Collection in progress (99/360) — final verdict pending.*

*All data collected live from Polymarket CLOB API and Binance REST API.*
*No synthetic, cached, or interpolated values used.*