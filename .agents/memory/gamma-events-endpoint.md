---
name: Gamma events endpoint
description: Which Gamma API endpoint returns deployed live events with populated markets
---

## Rule
Use `GET /events?series_slug={slug}&order=startDate&ascending=false&limit=20`
to fetch deployed live events with markets, conditionId, and clobTokenIds populated.

Do NOT use `GET /series?slug=` for event+market data — the `events[]` array embedded
in the series response contains **pre-staged** events that have empty `markets: []`
until the event is deployed to the CLOB.

**Why:** Two separate event lifecycles exist:
1. Pre-staged: visible in GET /series, have future endDates but `markets: []`
2. Deployed: visible via GET /events, have `markets[].clobTokenIds` populated

The series endpoint's events[] is NOT the same as the deployed events. They have
different IDs (series shows 609xxx pre-staged; events endpoint shows 610xxx deployed).

**How to apply:** In `gamma_series_client.py`, `fetch_events()` calls:
```
_get_with_retry("/events", {
    "series_slug": slug,
    "limit": limit,
    "order": "startDate",
    "ascending": "false",
})
```
The response is a flat list of event dicts, each with `markets[]` fully populated.
After fetching, filter out closed/past events and sort by `end_time` ascending so
index 0 is the active (soonest-expiring) market.

`fetch_series()` still calls GET /series?slug= (only needs id/slug/title metadata).
