---
name: Phase 12F — Active Market Live Order Flow Validation
description: Audit findings, fixes, and new fields for order flow classification on the price API; all 12 markets confirmed ACTIVE_SEED_ONLY as of 2026-07-12.
---

## Summary

Phase 12F completed 2026-07-12. A 17-step forensic audit confirmed:
- All 12 markets receive genuinely live, per-market CLOB data (individual HTTP calls per condition_id, 10s refresh)
- All 12 markets are `ACTIVE_SEED_ONLY` (volume=null, liquidity=null) — AMM init phase, no human trades yet
- Prices are constant at seed level (mid=0.505 for 5m/1H, mid=0.500 for 15m) with spread=0.01

## Bugs Fixed

1. **`yes_mid or SEED_PRICE` in `opportunity_engine.py:285`**  
   Changed to `yes_mid if yes_mid is not None else SEED_PRICE`. The old form would use SEED_PRICE=0.50 when `yes_mid=0.0` (falsy zero — valid Polymarket probability), silently zeroing out the deviation.

2. **`get_latest_active_markets()` missing time guards**  
   Added `or_()` NULL-safe `start_time <= now` and `end_time > now` guards to `market_price_repository.py`, matching `get_active_universe()`. Fixed `active_markets_with_data` count: 11→12.

## New Features Added

### Price API — 5 new fields on `PriceSnapshotResponse`
- `trading_activity_state`: ACTIVE_WITH_ORDER_FLOW | ACTIVE_SEED_ONLY | ACTIVE_STALE_BOOK | ACTIVE_DATA_MISSING
- `has_order_flow`: bool (volume > 0)
- `has_recent_trade`: bool (alias for has_order_flow; no per-tick data yet)
- `orderbook_fresh`: bool (captured_at <= 2× PRICE_REFRESH_SECONDS old)
- `price_data_mode`: SEED | LIVE_ORDER_FLOW | STALE | MISSING

Computed by `_classify_trading_activity()` in `api/v1/price.py`.

### Decision Engine — Step 0 Order Flow Pre-Check
Injected before Step 1 in `_decide_market()`. Uses `_price_get_latest()` to check volume. Outputs one of:
- `[Step 0] Order Flow: SEED_BOOK_ONLY — ... Reason: NO_ORDER_FLOW`
- `[Step 0] Order Flow: ACTIVE_WITH_ORDER_FLOW — volume=X.XX; real trades confirmed.`
- `[Step 0] Order Flow: PRICE_DATA_MISSING — ...`

### Frontend — CONF label
`renderCard()` reads `cp.price_data_mode`. If `SEED` or `MISSING`, CONF label shows `SEED` instead of `CONF`. When `LIVE_ORDER_FLOW`, shows `CONF` with actual confidence score.

## Test Coverage

`backend/app/tests/test_order_flow_validation.py` — 20 tests, all pass.

## Classification Rules

- `ACTIVE_WITH_ORDER_FLOW`: `volume is not None and volume > 0`
- `ACTIVE_SEED_ONLY`: volume null/0 AND snapshot age <= 2×PRICE_REFRESH_SECONDS
- `ACTIVE_STALE_BOOK`: snapshot age > 2×PRICE_REFRESH_SECONDS (regardless of volume)
- `ACTIVE_DATA_MISSING`: no snapshot in DB for this condition_id

## When Order Flow Arrives

When volume > 0 appears in CLOB data:
- API returns `trading_activity_state=ACTIVE_WITH_ORDER_FLOW, price_data_mode=LIVE_ORDER_FLOW`
- Decision Step 0 shows ACTIVE_WITH_ORDER_FLOW
- Frontend CONF label returns to showing confidence score
- Signal engine will emit MID_MOVE signals when yes_mid changes
- Opportunity scores will differentiate across markets

**Why:** AMM init phase markets share identical seed books. The architecture is correct; the uniformity is a Polymarket property, not a system bug. All values will diverge when real trading begins.
