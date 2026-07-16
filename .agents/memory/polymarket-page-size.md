---
name: Polymarket page size behaviour
description: Polymarket CLOB API returns ~1000 records per call despite limit=100; cursor advances by ~1000 per page
---

The Polymarket CLOB `/markets` endpoint ignores (or interprets differently) the `limit=100` query param. In practice each page yields ~1000 market records and the cursor offset increments by ~1000 per page.

**Why:** Observed empirically — after 250 pages the API returned 250,000 total markets, matching a Sprint 3 run that also showed 250k. Setting MAX_PAGES=2500 would scan 2.5M markets and take ~40 minutes; 250 pages ≈ 250k markets and completes in ~4 minutes.

**How to apply:** Keep `MAX_PAGES = 250` in `market_discovery.py`. If the page count ever needs tuning, remember that 1 page ≈ 1000 real records, not 100.
