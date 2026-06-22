# ACTIVE_LINKAGE_AUDIT.md

**Generated:** 2026-06-22 06:57:18 UTC
**Audit:** #5 — Part 4
**Method:** Pearson + Spearman correlation on returns; lag analysis at 10/20/30/60/120s
**Data source:** 30-minute monitoring window from Part 3
**Note:** Only ACTIVE replacement markets used (not expired contracts from prior audits).

## ETH/5m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 3.95

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## SOL/5m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.33

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## XRP/5m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.0053

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## BTC/5m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 201.19

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## ETH/15m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 2.192e-05  |  **Mid range:** 0.01
- **Spot range:** 3.95

### Correlation at Lag Offsets

| Lag (s) | Contemp. Pearson | Contemp. Spearman | Spot-Leads Pearson | Spot-Leads Spearman | Mkt-Leads Pearson | Mkt-Leads Spearman |
|---------|-----------------|-------------------|-------------------|--------------------|--------------------|---------------------|
| 10 | -0.0254 | 0.0639 | -0.0052 | 0.0604 | -0.007 | 0.083 |
| 20 | -0.0254 | 0.0639 | -0.0256 | 0.0548 | 0.0142 | 0.1069 |
| 30 | -0.0254 | 0.0639 | -0.0388 | 0.0555 | -0.1155 | 0.091 |
| 60 | -0.0254 | 0.0639 | -0.1591 | 0.06 | -0.0682 | 0.0892 |
| 120 | -0.0254 | 0.0639 | 0.0523 | 0.0541 | 0.0836 | 0.1083 |

**Linkage determination: NONE / NOISE** — correlation < 0.3, within noise floor.

## SOL/15m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.33

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## BTC/15m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 201.19

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## XRP/15m

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.0053

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## BTC/1H

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 201.19

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## XRP/1H

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.0053

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## ETH/1H

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 3.95

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## SOL/1H

- **Observations:** 180 paired (market mid, Binance spot)
- **Mid variance:** 0.0  |  **Mid range:** 0.0
- **Spot range:** 0.33

*Mid price did not move during observation — correlation is undefined.*

**Linkage determination: NONE** (no mid variance to correlate)

## Overall Linkage Summary

| Market | Mid Variance | Max |Pearson| | Linkage |
|--------|-------------|-----------------|---------|
| ETH/5m | 0 | N/A | NO VARIANCE |
| SOL/5m | 0 | N/A | NO VARIANCE |
| XRP/5m | 0 | N/A | NO VARIANCE |
| BTC/5m | 0 | N/A | NO VARIANCE |
| ETH/15m | 2.19e-05 | 0.159 | NONE |
| SOL/15m | 0 | N/A | NO VARIANCE |
| BTC/15m | 0 | N/A | NO VARIANCE |
| XRP/15m | 0 | N/A | NO VARIANCE |
| BTC/1H | 0 | N/A | NO VARIANCE |
| XRP/1H | 0 | N/A | NO VARIANCE |
| ETH/1H | 0 | N/A | NO VARIANCE |
| SOL/1H | 0 | N/A | NO VARIANCE |

---
*Analysis window: 30 minutes*