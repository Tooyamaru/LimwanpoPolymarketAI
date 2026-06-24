# PRICE_DISCOVERY_AUDIT.md

**Generated:** 2026-06-24 03:24:25 UTC
**Audit:** #5 — Part 2
**Observation window:** 60 rounds × 5s = 5 minutes
**Markets monitored:** 8

## Methodology

The CLOB `/trades` endpoint requires authentication and is not publicly accessible.
Trade events are inferred by detecting changes in `/last-trade-price` between consecutive
5-second polls. When LTP changes, the before/after order book is compared to determine
whether the bid, ask, mid, or only depth was affected.

## Event Tables

### BTC/15m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### BTC/5m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### ETH/15m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### ETH/5m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### SOL/15m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### SOL/5m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### XRP/15m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

### XRP/5m

| Metric | Count (5-min window) |
|--------|----------------------|
| LTP changes detected | 0 |
| Best bid changes | 0 |
| Best ask changes | 0 |
| Mid changes | 0 |
| Depth-only changes (no mid move) | 0 |

## Summary

| Event Type | Total Across All Markets |
|------------|--------------------------|
| LTP changes | 0 |
| Best bid changes | 0 |
| Mid changes | 0 |
| Depth-only changes | 0 |

**Conclusion:** No bid/ask price changes detected in 5-minute window.
Order books are static. If LTP changes occurred, they did not move the NBBO.

---
*Data fetched: 2026-06-24 03:24 UTC*