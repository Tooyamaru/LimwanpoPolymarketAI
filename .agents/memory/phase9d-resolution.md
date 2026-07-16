---
name: Phase 9D Direct Resolution
description: Outcome Learning now uses Gamma API as primary correctness source; PnL proxy is fallback only.
---

## Rule
`outcome_source` on every `outcome_learnings` row must be one of:
- `DIRECT_POLYMARKET_RESOLUTION` — Gamma confirmed `closed=True` + `outcomePrices` winner ≥ 0.99
- `REALIZED_PNL_PROXY` — Gamma not available; position PnL > 0 used as proxy
- `NOT_AVAILABLE` — no position taken and no direct resolution (e.g. WAIT, voided, unresolved)

**Why:** Phase 9B/9C audit caveat: correctness was derived from `realized_pnl > 0` only, which is a false-positive-prone proxy. Phase 9D closes this by calling `GET /markets?condition_ids={id}` on the Gamma API for every expired market before falling back to PnL.

**How to apply:**
- `outcome_learning_service._evaluate_market()` calls `gamma_client.fetch_market_resolution()` first
- BUY_YES correct ↔ `winning_side == "YES"` (not pnl sign)
- BUY_NO correct ↔ `winning_side == "NO"` (not pnl sign)
- realized_pnl still stored on the row as economic context — never used for correctness when DIRECT_POLYMARKET_RESOLUTION is set
- Voided markets (`["0","0"]` outcomePrices) → `NOT_AVAILABLE`, `correct=None`

## DB columns added (all nullable, ADD COLUMN IF NOT EXISTS)
`outcome_source VARCHAR(64)`, `winning_side VARCHAR(8)`, `winning_token_id VARCHAR(256)`,
`final_yes_price DOUBLE PRECISION`, `final_no_price DOUBLE PRECISION`, `resolution_note TEXT`

## Gamma endpoint
`GET https://gamma-api.polymarket.com/markets?condition_ids={condition_id}`
- `closed=True` required before checking outcomePrices
- `RESOLUTION_THRESHOLD = 0.99`
- conditionId matched case-insensitively (hex hashes can differ in capitalisation)
- `_parse_outcome_prices(raw)` handles None, empty, malformed, single-entry gracefully

## Test coverage
93 tests pass (18 new Phase 9D tests in test_gamma_series_client.py + test_outcome_learning_service.py)
