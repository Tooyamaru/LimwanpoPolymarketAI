# Sprint 9.1 — Active Market Lifecycle Fix Report

**Date:** 2026-06-19  
**Status:** ✅ COMPLETE — All success criteria met  
**Sprint 10 gate:** OPEN

---

## 1. Root-Cause Summary

### The Bug

The `sync()` method in `market_universe_service.py` assigned `effective_active = (idx == 0)` at the **Gamma event** level, then iterated over every market inside that event:

```python
for idx, event in enumerate(events):
    effective_active = idx == 0          # ← Event-level flag
    for market in event.markets:         # ← Applied to ALL markets in this event
        status = _determine_status(is_active=effective_active, ...)
```

**Failure mode A — multi-market events:** If a single Gamma event contained multiple markets with different `end_time` values (e.g. the 03:00 and 03:05 windows bundled inside one event object), every market inside `events[0]` received `status="active"`. The `created_at` timestamps in the audit (2–3 ms apart) confirmed both records were written in the same sync cycle from the same event.

**Failure mode B — stale active records:** Markets that were previously marked `active` in an earlier sync cycle, but whose `condition_id` no longer appeared in the current `fetch_events` top-20 response (because newer windows had pushed them off), retained their `active` status indefinitely. `expire_stale_markets()` only catches rows where `end_time < now`; a future-dated market with a stale `active` status is invisible to it.

Together these produced the observed count of **15–31 active markets** (fluctuating with Polymarket's window schedule) instead of the required **12**.

---

## 2. Code Changes

### 2a. `backend/app/services/market_universe_service.py`

**Changed:** `sync()` — replaced event-level `idx == 0` with market-level flattening and sorting.

```python
# BEFORE (buggy)
for idx, event in enumerate(events):
    effective_active = idx == 0
    for market in event.markets:
        status = _determine_status(is_active=effective_active, ...)
        await upsert_universe_market(...)

# AFTER (fixed)
# 1. Flatten all (end_time, event, market) tuples across every event
now = datetime.now(timezone.utc)
flat = []
for event in events:
    for market in event.markets:
        if market.is_closed:
            continue
        market_end = market.end_time or event.end_time
        if market_end is None or market_end <= now:
            continue
        flat.append((market_end, event, market))

# 2. Sort by market end_time ascending — rank 0 = soonest = active
flat.sort(key=lambda t: t[0])
active_condition_id = flat[0][2].condition_id if flat else None

for rank, (market_end, event, market) in enumerate(flat):
    effective_active = rank == 0      # ← Now market-level, not event-level
    status = _determine_status(is_active=effective_active, ...)
    await upsert_universe_market(...)

# 3. Demote any OTHER active records for this (asset, timeframe)
await demote_excess_active_markets(session, asset, timeframe, active_condition_id)
await expire_stale_markets(session)
await session.commit()
```

**Key properties of the fix:**
- Guarantees exactly one `active` market per `(asset, timeframe)` per sync cycle, regardless of how many consecutive windows Polymarket has open.
- Correctly handles events that contain multiple markets with different end_times.
- Filtered closed and past-end_time markets before ranking, so expired windows never compete for the active slot.
- Captures `active_condition_id` before opening the session so the demotion step always has the right value.

### 2b. `backend/app/services/universe_repository.py`

**Added:** `demote_excess_active_markets()` — a targeted UPDATE that sets every `active` market for a given `(asset, timeframe)` that is **not** the chosen `keep_condition_id` back to `upcoming`.

```python
async def demote_excess_active_markets(
    session: AsyncSession,
    asset: str,
    timeframe: str,
    keep_condition_id: Optional[str],
) -> int:
    now = datetime.now(timezone.utc)
    stmt = (
        update(MarketUniverse)
        .where(
            MarketUniverse.asset == asset,
            MarketUniverse.timeframe == timeframe,
            MarketUniverse.status == "active",
            MarketUniverse.condition_id != keep_condition_id
            if keep_condition_id
            else True,
        )
        .values(status="upcoming", updated_at=now)
    )
    result = await session.execute(stmt)
    return result.rowcount
```

This handles Failure Mode B: stale active records that fell off the `fetch_events` page but whose `end_time` is still in the future.

---

## 3. Test Results

### Test suite: `test_market_universe_service.py`

```
collected 23 items

PASSED  test_determine_status_closed_is_expired
PASSED  test_determine_status_past_end_time_is_expired
PASSED  test_determine_status_active_flag_is_active
PASSED  test_determine_status_future_start_time_is_upcoming
PASSED  test_determine_status_no_flags_defaults_upcoming
PASSED  test_series_catalog_has_12_entries
PASSED  test_series_catalog_has_all_assets
PASSED  test_series_catalog_has_all_timeframes
PASSED  test_series_catalog_all_have_slugs
PASSED  test_series_catalog_slugs_are_unique
PASSED  test_sync_returns_summary_dict
PASSED  test_sync_processes_all_12_series
PASSED  test_sync_last_sync_is_set_after_run
PASSED  test_sync_errors_are_collected_not_raised
PASSED  test_sync_marks_first_event_active
PASSED  test_sync_marks_remaining_events_upcoming
PASSED  test_sprint91_three_consecutive_5m_windows_only_first_active  ← Case A
PASSED  test_sprint91_two_markets_same_event_only_soonest_active      ← Case A (multi-market)
PASSED  test_sprint91_single_market_is_active                         ← Case B
PASSED  test_sprint91_expired_market_is_not_active                    ← Case C
PASSED  test_sprint91_max_one_active_per_series                       ← Case D
PASSED  test_sprint91_no_active_when_all_markets_expired              ← Case C (all expired)
PASSED  test_sync_upserts_only_events_returned_by_fetch_events

======================== 23 passed in 0.51s =========================
```

### Sprint 9.1 test coverage (Cases A–D)

| Case | Description | Test | Result |
|------|-------------|------|--------|
| A | Three consecutive 5m windows (03:00/03:05/03:10) → only 03:00 active | `test_sprint91_three_consecutive_5m_windows_only_first_active` | ✅ PASS |
| A (variant) | Two markets inside the SAME Gamma event → only soonest active | `test_sprint91_two_markets_same_event_only_soonest_active` | ✅ PASS |
| B | Single market → active | `test_sprint91_single_market_is_active` | ✅ PASS |
| C | Expired market not active; future market becomes active | `test_sprint91_expired_market_is_not_active` | ✅ PASS |
| C (all expired) | All markets past end_time → zero active | `test_sprint91_no_active_when_all_markets_expired` | ✅ PASS |
| D | Six open markets for a series → exactly one active | `test_sprint91_max_one_active_per_series` | ✅ PASS |

---

## 4. Live Validation Results

Live sync triggered at: `2026-06-19T05:02:11Z`

### SQL 1: Active count by asset / timeframe

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
ETH,5m,1
SOL,15m,1
SOL,1H,1
SOL,5m,1
XRP,15m,1
XRP,1H,1
XRP,5m,1
```
✅ 12 rows, all counts = 1

### SQL 2: Total active count

```sql
SELECT COUNT(*) FROM market_universe WHERE status = 'active';
```

**Result:** `12` ✅

### SQL 3: Duplicate check

```sql
SELECT asset, timeframe, COUNT(*)
FROM market_universe WHERE status='active'
GROUP BY asset, timeframe HAVING COUNT(*) > 1;
```

**Result:** *(no rows)* ✅

### Full active market listing (post-fix)

```
BTC,15m  → 0x784c9637...  end: 2026-06-20 00:15
BTC,1H   → 0x4048f518...  end: 2026-06-20 10:00
BTC,5m   → 0xa224bc45...  end: 2026-06-20 03:15
ETH,15m  → 0x56000f42...  end: 2026-06-20 00:15
ETH,1H   → 0x89761ea9...  end: 2026-06-20 10:00
ETH,5m   → 0xed9f5747...  end: 2026-06-20 03:15
SOL,15m  → 0x1df2b1c4...  end: 2026-06-19 23:30
SOL,1H   → 0x549196...    end: 2026-06-20 10:00
SOL,5m   → 0x817265ff...  end: 2026-06-20 03:15
XRP,15m  → 0x115788e8...  end: 2026-06-20 00:15
XRP,1H   → 0xa7280fd4...  end: 2026-06-20 10:00
XRP,5m   → 0x6295c74f...  end: 2026-06-20 03:15
```

### Price stats endpoint

```
GET /api/v1/price/stats

{
  "total_snapshots": 532,
  "active_markets_with_data": 12,
  "assets_covered": ["BTC", "ETH", "SOL", "XRP"],
  "timeframes_covered": ["15m", "1H", "5m"]
}
```
✅ `active_markets_with_data: 12` — price refresh now tracks exactly 12 markets

---

## 5. Success Criteria Checklist

| Criterion | Result |
|-----------|--------|
| All tests pass | ✅ 23/23 |
| Active count = 12 | ✅ 12 |
| No duplicate active markets | ✅ Zero duplicates |
| Exactly one active per (asset, timeframe) | ✅ All 12 slots = count of 1 |
| Price refresh consumes exactly 12 active markets | ✅ `active_markets_with_data: 12` |
| Sprint 10 can safely begin | ✅ Yes |

---

## 6. Invariant Going Forward

Every sync cycle now:

1. **Flattens** all markets across all events for a series
2. **Filters** out closed markets and markets with `end_time ≤ now`
3. **Sorts** the flat list by `market.end_time` ascending
4. **Marks rank-0** (soonest expiry) as `active`, all others `upcoming`
5. **Demotes** any other existing `active` record for that `(asset, timeframe)` to `upcoming` — regardless of whether its `condition_id` appeared in the current fetch

This is a self-healing mechanism: even if a bug or network error introduces a stale `active` record, the next sync cycle will correct it automatically.
