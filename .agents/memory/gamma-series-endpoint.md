---
name: Gamma series endpoint
description: Which Gamma API endpoint returns live vs historical events for a series
---

## Rule
Use `GET /series?slug={slug}` to fetch live events for a series.
Do NOT use `GET /events?series_slug={slug}` — that returns only historical (expired) events.

**Why:** The `/events` endpoint is ordered by creation date descending and returns all past events. The `/series` endpoint embeds up to 20 currently-live events in `response[0]["events"]` — the same data source used by the Polymarket website frontend.

**How to apply:** In `gamma_series_client.py`, `fetch_events()` calls `_get_with_retry("/series", {"slug": series_slug})` and extracts `rows[0].get("events", [])`. Any future method that needs live event data must follow the same pattern.
