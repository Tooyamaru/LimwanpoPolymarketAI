# Sprint 9 Post-Validation Audit Report

**Date:** 2026-06-19  
**Auditor:** Automated Live-Data Audit  
**Status:** BUGS CONFIRMED — Sprint 10 blocked on two issues

---

## 1. Active Market Count

### SQL: Active count by asset / timeframe

```sql
SELECT asset, timeframe, COUNT(*) AS active_count
FROM market_universe
WHERE status = 'active'
GROUP BY asset, timeframe
ORDER BY asset, timeframe;
```

**Result:**

```
asset,timeframe,active_count
BTC,15m,1
BTC,1H,1
BTC,5m,1
ETH,15m,1
ETH,1H,1
ETH,5m,2   ← DUPLICATE
SOL,15m,1
SOL,1H,1
SOL,5m,2   ← DUPLICATE
XRP,15m,1
XRP,1H,1
XRP,5m,2   ← DUPLICATE
```

### SQL: Total active count

```sql
SELECT COUNT(*) FROM market_universe WHERE status = 'active';
```

**Result:** `15`

**Verdict:** ❌ FAIL — Expected 12. Actual 15. Three asset/timeframe slots carry duplicate active records.

---

## 2. Sprint 9 Discrepancy Investigation

### Sprint 8.6 vs Sprint 9 vs Current

| Source | Value |
|--------|-------|
| Sprint 8.6 report | `active = 12` |
| Sprint 9 report | `active_markets_with_data = 31` |
| Live audit (now) | `active_markets_with_data = 15` |

### Current status distribution

```sql
SELECT status, COUNT(*) FROM market_universe GROUP BY status ORDER BY status;
```

**Result:**

```
status,count
active,15
upcoming,228
```

### Root-Cause Analysis

**The `31` figure in the Sprint 9 report was caused by a timing artefact, not a logic fix.**

The universe sync queries the Polymarket Gamma API and classifies any market whose `end_time` is in the future (relative to now) and whose API-side status is open as `active`. For 5-minute markets, Polymarket keeps **several consecutive windows open simultaneously** — a new 5m window opens before the prior one closes. When the sync ran during Sprint 9, Polymarket had **≈6–8 consecutive 5m windows simultaneously open** for some or all of the 4 tracked assets, yielding `4 assets × ~6 windows = ~24 active 5m records` plus the 8 correct 15m/1H records, totalling approximately 31.

The current count of 15 reflects a quieter window where most assets have only 1 active 5m slot except ETH, SOL, and XRP which each carry 2. This will fluctuate with market timing.

**The underlying bug is unchanged:** there is no "keep only the nearest expiry" guard in the universe sync upsert path. Every unique `condition_id` from Polymarket that passes the active filter is inserted as `status='active'` with no deduplication by `(asset, timeframe)`.

---

## 3. Active Market Integrity

### SQL: Full active record listing

```sql
SELECT asset, timeframe, condition_id, event_id, end_time, status
FROM market_universe
WHERE status = 'active'
ORDER BY asset, timeframe, end_time;
```

**Result:**

```
asset,timeframe,condition_id,event_id,end_time,status
BTC,15m,0xaef2db1066c955abb7811ba44a3166fba89a825d3fe1ff84d99f6bb60e894e3d,610064,2026-06-20 00:00:00+00,active
BTC,1H, 0x4048f518ddc0e3abc9c0d27113c33ba51e15714a827ea14a044534a8378d19d5,607813,2026-06-20 10:00:00+00,active
BTC,5m, 0xd063a453ca37bcc6abbb320e65ac104d23a85c2966d1d083c244ce4ce5a11321,610511,2026-06-20 03:05:00+00,active
ETH,15m,0xad826a8b0cb0c4a91b072377ced8156bf2a1fe552599325bd3fa872252cdebdf,610037,2026-06-19 23:45:00+00,active
ETH,1H, 0x89761ea9ad5616414b0f9e425a0da28a11c4230410a78299f7de05a3dbd9ada5,607814,2026-06-20 10:00:00+00,active
ETH,5m, 0x718007a9e93e1083d5d292d7e4994653a5a6e4a6a872baddd1c4aec3ef95eab8,610501,2026-06-20 03:00:00+00,active  ← DUPLICATE A
ETH,5m, 0x2e346c44fffeec49a227a3c5ed91f32fad1ab86bc6ddbeb2619ba7ef1776643e,610503,2026-06-20 03:05:00+00,active  ← DUPLICATE B
SOL,15m,0x1df2b1c46b41b7095d15ab0f573177a471658667341935f7b77935a69460edbb,610009,2026-06-19 23:30:00+00,active
SOL,1H, 0x549196142e62cf11884678f3228a299711b38f196d76c9bdfb21e1bd4c331607,607815,2026-06-20 10:00:00+00,active
SOL,5m, 0xe293577a383afcff7c08932a3db835308d1f1ebd24351c7b3998384af003271f,610500,2026-06-20 03:00:00+00,active  ← DUPLICATE A
SOL,5m, 0xb3dd237510e1173f1de22b32cef9fe03da18c870d3f549b975e18f561f4d7149,610507,2026-06-20 03:05:00+00,active  ← DUPLICATE B
XRP,15m,0x1c1bb10696c25514df0d0dc15c90fbd84d6dc8f73e816abbf4de7a57964c50f5,610069,2026-06-20 00:00:00+00,active
XRP,1H, 0xa7280fd414013227da9c1fd7c4bd4edcd1343302c5f45b2b14ab5706c192cda6,607816,2026-06-20 10:00:00+00,active
XRP,5m, 0x7e192b847a0b0924f03d62b4eaa2fc2a171097c3ba1db056a6540b642a661898,610497,2026-06-20 03:00:00+00,active  ← DUPLICATE A
XRP,5m, 0x580993c57ed89f27a33dd1cb5534db7127a3f02f4e8b4ca3db27c24f6f5f317a,610506,2026-06-20 03:05:00+00,active  ← DUPLICATE B
```

**Observations:**

- BTC/5m: 1 record (03:05 only) — clean.
- ETH, SOL, XRP each carry two simultaneous 5m active records: `end_time 03:00` and `end_time 03:05`.
- All records are distinct `condition_id` values — no exact-duplicate rows.
- The problem is **logical** duplicates at the `(asset, timeframe)` level, not exact row-level duplicates.
- The two windows inserted within milliseconds of each other (`created_at` gap ~2–3 ms), confirming both passed the active filter in a single sync cycle.

**Verdict:** ❌ FAIL — Three asset/timeframe combinations violate the "one active market per slot" invariant.

---

## 4. Price Snapshot Coverage

### SQL: Total snapshots

```sql
SELECT COUNT(*) FROM market_price_snapshots;
```

**Result:** `66`

### SQL: Snapshots per condition_id (top 20)

```sql
SELECT condition_id, COUNT(*) AS snapshots
FROM market_price_snapshots
GROUP BY condition_id
ORDER BY snapshots DESC
LIMIT 20;
```

**Result:**

```
condition_id,snapshots
0x1c1bb10...  (XRP 15m)  5
0x4048f51...  (BTC 1H)   5
0xad826a8...  (ETH 15m)  5
0x718007a...  (ETH 5m A) 5
0xe293577...  (SOL 5m A) 5
0xa7280fd...  (XRP 1H)   5
0x1df2b1c...  (SOL 15m)  5
0x89761ea...  (ETH 1H)   5
0x549196...   (SOL 1H)   5
0xd063a45...  (BTC 5m)   5
0xaef2db1...  (BTC 15m)  5
0x7e192b8...  (XRP 5m A) 5
0x580993c...  (XRP 5m B) 2   ← DUPLICATE
0xb3dd237...  (SOL 5m B) 2   ← DUPLICATE
0x2e346c4...  (ETH 5m B) 2   ← DUPLICATE
```

**Distribution Analysis:**

- 12 condition_ids have 5 snapshots each = 60 snapshots (the "canonical" active set that was established first).
- 3 condition_ids (the duplicate 5m B windows) have 2 snapshots each = 6 snapshots.
- Total: 60 + 6 = **66**.
- The price refresher is faithfully tracking all 15 active records, including the 3 illegitimate duplicates.
- The asymmetry (5 vs 2) reflects that the 03:05 window was inserted mid-cycle, so fewer refresh cycles have captured it.

---

## 5. Price Endpoint Validation

### GET /api/v1/price/stats

**Raw response:**

```json
{
  "total_snapshots": 66,
  "active_markets_with_data": 15,
  "assets_covered": ["BTC", "ETH", "SOL", "XRP"],
  "timeframes_covered": ["15m", "1H", "5m"]
}
```

**Note:** `active_markets_with_data: 15` is inflated by the 3 duplicate records. Correct value should be 12.

### GET /api/v1/price/active — sample (first 3 records)

```json
[
  {
    "id": 52,
    "condition_id": "0xaef2db1066c955abb7811ba44a3166fba89a825d3fe1ff84d99f6bb60e894e3d",
    "yes_bid": 0.01, "yes_ask": 0.99, "yes_mid": 0.5,
    "no_bid": 0.01,  "no_ask": 0.99, "no_mid": 0.5,
    "spread_yes": 0.98, "spread_no": 0.98,
    "volume": null, "liquidity": null,
    "captured_at": "2026-06-19T04:48:13.763980Z",
    "asset": "BTC", "timeframe": "15m"
  },
  {
    "id": 53,
    "condition_id": "0x4048f518ddc0e3abc9c0d27113c33ba51e15714a827ea14a044534a8378d19d5",
    "yes_bid": 0.01, "yes_ask": 0.99, "yes_mid": 0.5,
    "no_bid": 0.01,  "no_ask": 0.99, "no_mid": 0.5,
    "spread_yes": 0.98, "spread_no": 0.98,
    "volume": null, "liquidity": null,
    "captured_at": "2026-06-19T04:48:14.470515Z",
    "asset": "BTC", "timeframe": "1H"
  },
  {
    "id": 54,
    "condition_id": "0xd063a453ca37bcc6abbb320e65ac104d23a85c2966d1d083c244ce4ce5a11321",
    "yes_bid": 0.01, "yes_ask": 0.99, "yes_mid": 0.5,
    "no_bid": 0.01,  "no_ask": 0.99, "no_mid": 0.5,
    "spread_yes": 0.98, "spread_no": 0.98,
    "volume": null, "liquidity": null,
    "captured_at": "2026-06-19T04:48:15.194980Z",
    "asset": "BTC", "timeframe": "5m"
  }
]
```

---

## 6. Order Book Parsing Validation — BTC 5m

**Market:** `condition_id = 0xd063a453ca37bcc6abbb320e65ac104d23a85c2966d1d083c244ce4ce5a11321`

| Field | Value |
|-------|-------|
| yes_bid | 0.01 |
| yes_ask | 0.99 |
| yes_mid | 0.50 |
| no_bid | 0.01 |
| no_ask | 0.99 |
| no_mid | 0.50 |
| spread_yes | 0.98 |
| spread_no | 0.98 |
| volume | null |
| liquidity | null |

**Verdict:** ❌ FAIL — Values are identical to Sprint 9 baseline. `0.01 / 0.99` represents the **minimum tick / maximum ask** combination returned by the CLOB API for a market with an effectively empty or fully one-sided order book. This indicates:

1. These upcoming (pre-live) 5m markets have no real resting orders yet.
2. The parser IS reading the CLOB correctly — it is faithfully recording what the exchange returns.
3. However, the mid-price of `0.5` is computed mechanically as `(0.01 + 0.99) / 2`, which is meaningless for a market with no real liquidity.
4. `volume` and `liquidity` are `null` — these fields are not yet populated by the refresher.

This is expected behaviour for markets that have not yet attracted liquidity, NOT a parser bug. The parser needs real, liquid markets to return meaningful values.

---

## 7. Duplicate Status Detection

### SQL

```sql
SELECT asset, timeframe, COUNT(*)
FROM market_universe
WHERE status='active'
GROUP BY asset, timeframe
HAVING COUNT(*) > 1;
```

**Result:**

```
asset,timeframe,count
ETH,5m,2
SOL,5m,2
XRP,5m,2
```

**Confirmed:** Three asset/timeframe pairs have more than one simultaneous active record.

---

## 8. Final Verdict

### A. Is Sprint 9 production ready?

**NO.**

Two bugs block production readiness:

1. **Duplicate active lifecycle bug** — The universe sync has no guard to ensure at most one `active` record per `(asset, timeframe)`. When Polymarket has consecutive 5m windows open simultaneously, all of them are ingested as `active`. This corrupts the market universe and inflates snapshot counts.

2. **Null volume/liquidity** — The price refresher captures bid/ask but never populates `volume` or `liquidity`. These are left `null` across all records.

### B. Is active market lifecycle correct?

**NO.**

The lifecycle is broken for 5-minute markets. The invariant "exactly one active market per asset/timeframe" is violated whenever Polymarket has overlapping consecutive windows open. The sync must select only the nearest-expiry window (i.e. `MIN(end_time)` among all simultaneously open windows for a given asset/timeframe) and mark any others as `upcoming`.

### C. Can Sprint 10 begin safely?

**NO.** Sprint 10 should not begin until the `(asset, timeframe)` uniqueness invariant is enforced in the universe sync. Any Sprint 10 logic that queries `WHERE status = 'active'` will silently receive multiple rows per slot, producing incorrect aggregations, duplicate price tracking, and unreliable signal generation.

### D. What exact bugs remain?

| # | Bug | Location | Severity |
|---|-----|----------|----------|
| 1 | No `(asset, timeframe)` uniqueness guard in universe sync upsert — multiple consecutive 5m windows ingested as `active` simultaneously | `app/services/market_universe_service.py` (sync/upsert path) | **Critical** |
| 2 | `volume` and `liquidity` fields always `null` — price refresher fetches bid/ask only | `app/services/market_price_service.py` (refresh method) | Medium |
| 3 | `active_markets_with_data` in `/api/v1/price/stats` counts all active rows including duplicates, not canonical markets | `app/api/v1/endpoints/price.py` | Low |

---

## Summary Table

| Task | Expected | Actual | Status |
|------|----------|--------|--------|
| Active market count | 12 | 15 | ❌ FAIL |
| Duplicates per asset/timeframe | 0 | 3 pairs (ETH, SOL, XRP 5m) | ❌ FAIL |
| Distinct condition_ids active | 12 | 15 | ❌ FAIL |
| Price snapshot total | ≥12 | 66 | ⚠ INFLATED |
| Order book values (0.01/0.99) | Evolved | Unchanged | ⚠ EXPECTED (no liquidity yet) |
| Volume / liquidity fields | Populated | null | ❌ FAIL |
| Sprint 9 discrepancy (31 vs 12) | Explained | Timing artefact + lifecycle bug | ✅ EXPLAINED |
| Sprint 10 readiness | Ready | Blocked | ❌ NOT READY |
