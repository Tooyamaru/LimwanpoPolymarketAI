---
name: CLOB book sort order
description: Polymarket CLOB /book endpoint sort order for bids and asks arrays
---

The Polymarket CLOB `/book` endpoint returns:
- `bids`: sorted **ASCENDING** by price (lowest first: 0.01, 0.02 … 0.49)
- `asks`: sorted **DESCENDING** by price (highest first: 0.99, 0.98 … 0.51)

Therefore:
- `best_bid = bids[-1]["price"]` (last element = highest price)
- `best_ask = asks[-1]["price"]` (last element = lowest price)

**Why:** Verified with raw JSON from 3 tokens in Sprint 9.4. The comment in the original code said the opposite ("bids descending, index 0 = best bid") — that was wrong. DEF-001 fix was applied to `backend/app/services/clob_client.py`.

**How to apply:** Any code that reads `bids[0]` or `asks[0]` as best bid/ask is using the WRONG value (returns worst bid 0.01 / worst ask 0.99, spread=0.98 instead of correct 0.02).
