---
name: Market Reference Service
description: Phase Next feature — backend-owned opening_price (Price to Beat) fetched from Binance once per market at discovery.
---

# Market Reference Service

## The Rule
`opening_price` is fetched from Binance exactly once per market (when `opening_price IS NULL`), aligned to the candle boundary containing `market.start_time`, and stored permanently. Frontend reads `market.opening_price` from the API — no client-side candle fetching.

## Key Implementation Points
- `backend/app/services/market_reference_service.py` — standalone service; uses `get_logger(__name__)` (structlog), NOT `logging.getLogger`
- Candle alignment: `start_ms = (raw_ms // interval_ms) * interval_ms` — critical for 1H markets; without alignment Binance returns empty list
- DB update is conditional: `WHERE condition_id=:id AND opening_price IS NULL` — prevents concurrent sync runs from overwriting a resolved value
- Triggered in `market_universe_service.sync()` AFTER session commit (pending_refs list)
- Fields added: `opening_price`, `opening_price_source`, `opening_price_timestamp`, `reference_status` (PENDING/READY)
- Upcoming markets (start_time in future) are left PENDING and retried on next sync

**Why:** Architecture doc ("Phase Next") requires all Price-to-Beat logic off the frontend. Candle alignment was needed because Polymarket `start_time` is not always on a candle boundary.

**How to apply:** When adding new timeframes (4H, 1D, etc.), add entry to both `TF_INTERVAL` and `INTERVAL_DURATION_MS` dicts in `market_reference_service.py`.
