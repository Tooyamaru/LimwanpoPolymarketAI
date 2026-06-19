# Sprint 8.5 Fix Report — Universe Engine Bug Fixes

**Date:** 2026-06-19  
**Status:** COMPLETE ✅  
**Tests:** 239 / 239 passing

---

## Overview

Sprint 8.5 fixed two root-cause bugs in the Universe Engine (Sprint 7) that caused all 240 stored markets to be expired and all token IDs to be null.  Both bugs were in `gamma_series_client.py`.

---

## Bug 1 — Wrong API Endpoint (fetch_events)

### Root Cause
`fetch_events` was calling `GET /events?series_slug={slug}&limit=20`.  
This endpoint returns **historical (already-expired) events** ordered by creation date descending.  By the time the code ran, every returned event had already expired, which is why the DB showed 240 markets all in `expired` status.

### Fix
Changed `fetch_events` to call `GET /series?slug={slug}`.  
This endpoint returns the series object with its **currently live events** embedded in the `events[]` array — the same source used by the Polymarket website.  The embedded events list contains up to 20 open/upcoming events sorted by `endDate` ascending.

```python
# Before (wrong)
rows = await self._get_with_retry(
    "/events",
    params={"series_slug": series_slug, "limit": limit},
)

# After (correct)
rows = await self._get_with_retry(
    "/series",
    params={"slug": series_slug},
)
series_data = rows[0] if rows else {}
event_rows = series_data.get("events", [])
```

---

## Bug 2 — Wrong Token Field (clobTokenIds)

### Root Cause
`GammaMarketRaw` had a `tokens: list[GammaToken]` field expecting:
```json
"tokens": [{"token_id": "...", "outcome": "Yes"}, ...]
```
This field **does not exist** in the Gamma API response.  The actual field is:
```json
"clobTokenIds": "[\"<yes_token_id>\", \"<no_token_id>\"]"
```
It is a JSON-encoded string, index 0 = YES token, index 1 = NO token.  Because `tokens` was always empty, `yes_token_id` and `no_token_id` were always null in the DB.

### Fix
- Removed `GammaToken` class and `tokens` field entirely.
- Added `clob_token_ids: Optional[str] = Field(None, alias="clobTokenIds")` to `GammaMarketRaw`.
- Replaced `_extract_tokens(tokens_list)` with `_extract_clob_token_ids(clob_token_ids_str)` which parses the JSON string and returns `(yes_id, no_id)`.

```python
def _extract_clob_token_ids(
    clob_token_ids: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if not clob_token_ids:
        return None, None
    try:
        ids = json.loads(clob_token_ids)
        yes_id = str(ids[0]) if len(ids) > 0 else None
        no_id  = str(ids[1]) if len(ids) > 1 else None
        return yes_id, no_id
    except (json.JSONDecodeError, IndexError, TypeError, ValueError):
        return None, None
```

---

## Bonus Fix — Active vs Upcoming Status

### Root Cause
The Gamma series endpoint returns all ~20 embedded events with `active=True, closed=False`.  The old `_determine_status` logic checked `is_active` first, so every market was stored with `status="active"` instead of only one per series.

### Fix
`MarketUniverseService.sync()` now sorts the open events by `end_time` ascending before upserting.  Only the event at index 0 (soonest expiry = currently trading) is marked `effective_active=True`; all subsequent events receive `effective_active=False` → `status="upcoming"`.  `expire_stale_markets()` continues to handle cleanup of past-endDate rows.

```python
open_events = [e for e in events if not e.is_closed and e.end_time and e.end_time > now]
open_events.sort(key=lambda e: e.end_time)

for idx, event in enumerate(open_events):
    effective_active = idx == 0          # only the first is "active"
    for market in event.markets:
        status = _determine_status(
            is_active=effective_active, ...
        )
```

Expected universe shape after next sync (per series):
- 1 market with `status="active"` (soonest endDate > now)
- ~19 markets with `status="upcoming"`

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/gamma_series_client.py` | Bug 1 + Bug 2 fixes; `GammaToken` removed; `_extract_clob_token_ids` added |
| `backend/app/services/market_universe_service.py` | Sort-by-endDate + effective_active fix in `sync()` |
| `backend/app/tests/test_gamma_series_client.py` | Full rewrite: old token tests replaced, new series-format / clobTokenIds / sorting tests added |
| `backend/app/tests/test_market_universe_service.py` | 3 new tests: active assignment, upcoming assignment, closed event exclusion |

---

## Test Coverage Added (Sprint 8.5)

### `test_gamma_series_client.py` — new tests
- `test_extract_clob_token_ids_valid`
- `test_extract_clob_token_ids_none_input`
- `test_extract_clob_token_ids_empty_string`
- `test_extract_clob_token_ids_malformed_json`
- `test_extract_clob_token_ids_single_entry`
- `test_extract_clob_token_ids_numeric_token_ids`
- `test_extract_clob_token_ids_first_is_yes`
- `test_fetch_events_parses_yes_token_from_clob_token_ids`
- `test_fetch_events_parses_no_token_from_clob_token_ids`
- `test_fetch_events_series_with_no_events_key`
- `test_fetch_events_multiple_events_parsed`
- `test_fetch_events_real_clob_token_ids_format`
- `test_fetch_active_market_returns_soonest_expiring`
- `test_fetch_active_market_skips_closed_events`
- `test_fetch_next_markets_returns_upcoming_after_active`
- `test_fetch_next_markets_respects_count_limit`
- `test_fetch_next_markets_empty_when_only_one_event`

### `test_market_universe_service.py` — new tests
- `test_sync_marks_first_event_active`
- `test_sync_marks_remaining_events_upcoming`
- `test_sync_skips_closed_events`

---

## Next Steps

1. Run a live sync via `POST /api/v1/universe/sync`
2. Verify `GET /api/v1/universe/active` returns 12 markets (one per series) with token IDs populated
3. Sprint 9: price feed integration using the YES/NO token IDs now correctly populated
