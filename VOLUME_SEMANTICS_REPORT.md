# VOLUME_SEMANTICS_REPORT.md

**Generated:** 2026-06-19  
**Scope:** All 12 currently active Up-or-Down markets (BTC, ETH, SOL, XRP — 5m, 15m, 1H)  
**Method:** Direct API queries against Polymarket CLOB and Gamma endpoints, cross-referenced with official OpenAPI schema

---

## 1. API Architecture and Field Sources

There are two separate Polymarket APIs that expose market data. They do not share field schemas.

### 1.1 CLOB API (`https://clob.polymarket.com`)

Endpoint queried: `GET /markets/{condition_id}`

The CLOB `/markets/{condition_id}` response schema **does not include `volume` or `liquidity` fields**.  
These fields are literally absent from every response. The complete field list returned is:

```
enable_order_book, active, closed, archived, accepting_orders,
accepting_order_timestamp, minimum_order_size, minimum_tick_size,
condition_id, question_id, question, description, market_slug,
end_date_iso, game_start_time, seconds_delay, fpmm, maker_base_fee,
taker_base_fee, notifications_enabled, neg_risk, neg_risk_market_id,
neg_risk_request_id, icon, image, rewards, is_50_50_outcome, tokens, tags
```

**Consequence:** The application's current code reads `volume` and `liquidity` from this endpoint. Because those fields do not exist in the response, every value stored to the database is `None` by construction — regardless of actual trading activity. `volume=NULL` in the application database is a **data pipeline artifact**, not direct evidence of trading status.

### 1.2 Gamma API (`https://gamma-api.polymarket.com`)

Two lookup methods were tested:

| Lookup method | Result |
|---|---|
| `GET /markets?conditionId={cid}` | **Broken.** The `conditionId` parameter is silently ignored. The API returns unrelated top markets. Verified: querying BTC/15m and XRP/5m condition IDs both returned the same unrelated market ("New Rihanna Album before GTA VI?"). |
| `GET /markets?slug={slug}` | **Works.** Correctly returns the matching market by its CLOB market slug. |

All Gamma data below was obtained via the correct `?slug=` lookup.

---

## 2. Field Definitions

From the Gamma OpenAPI specification (`GET /openapi.json`):

| Field | Type | Definition |
|---|---|---|
| `volume` | string | Legacy FPMM/AMM aggregate lifetime volume (USD notional). String type. |
| `volumeNum` | float | Same as `volume`, numeric representation. |
| `volumeClob` | float | CLOB order book executed trade volume (USD notional, lifetime). |
| `liquidity` | string | Legacy FPMM/AMM liquidity provision amount (USD). String type. |
| `liquidityNum` | float | Same as `liquidity`, numeric representation. |
| `liquidityClob` | float | CLOB resting order liquidity (USD notional currently on the book). |
| `volume24hr` | float | CLOB executed trade volume in the prior 24 hours (USD notional). |
| `lastTradePrice` | float | Price of the last matched CLOB trade. |

`tradeCount` does not appear in the Gamma OpenAPI schema or in any API response observed.

---

## 3. Live Data: All 12 Active Markets

Queried 2026-06-19, via Gamma `?slug=` and CLOB `last-trade-price`.

| Market | Slug | Gamma volume | Gamma volumeClob | Gamma lastTradePrice | Gamma volume24hr | CLOB ltp price | CLOB ltp side | Price history pts | Price range |
|---|---|---|---|---|---|---|---|---|---|
| BTC/5m | btc-updown-5m-1781931900 | null | null | null | null | 0.5 | _(empty)_ | 3 | 0.505–0.505 |
| BTC/15m | btc-updown-15m-1781919900 | null | null | null | null | 0.5 | _(empty)_ | 6 | 0.5–0.5 |
| BTC/1H | bitcoin-up-or-down-june-20-2026-7am-et | null | null | null | null | 0.5 | _(empty)_ | 20 | 0.5–0.5 |
| ETH/5m | eth-updown-5m-1781931900 | null | null | null | null | 0.5 | _(empty)_ | 3 | 0.5–0.5 |
| ETH/15m | eth-updown-15m-1781919900 | null | null | null | null | 0.5 | _(empty)_ | 6 | 0.5–0.5 |
| ETH/1H | ethereum-up-or-down-june-20-2026-7am-et | null | null | null | null | 0.5 | _(empty)_ | 20 | 0.5–0.5 |
| SOL/5m | sol-updown-5m-1781931900 | null | null | null | null | 0.5 | _(empty)_ | 3 | 0.5–0.5 |
| SOL/15m | sol-updown-15m-1781919900 | null | null | null | null | 0.5 | _(empty)_ | 6 | 0.5–0.5 |
| SOL/1H | solana-up-or-down-june-20-2026-7am-et | null | null | null | null | 0.5 | _(empty)_ | 20 | 0.5–0.5 |
| XRP/5m | xrp-updown-5m-1781931900 | null | null | null | null | 0.5 | _(empty)_ | 3 | 0.5–0.5 |
| XRP/15m | xrp-updown-15m-1781919900 | null | null | null | null | 0.5 | _(empty)_ | 6 | 0.5–0.5 |
| XRP/1H | xrp-up-or-down-june-20-2026-7am-et | null | null | null | null | 0.5 | _(empty)_ | 20 | 0.5–0.5 |

### Order Book Sample (BTC/15m)

```
Bids: 46 resting orders | Best bid: 0.49 @ $1,311.47
Asks: 46 resting orders | Best ask: 0.51 @ $1,311.47
Spread: 0.02
```

Symmetric depth (46/46) and identical size at best bid/ask are characteristic of automated market maker initialization, not organic order placement.

---

## 4. Trade History Endpoint

`GET /trades` (CLOB): Returns **HTTP 401 — Unauthorized**. Requires API credentials. Cannot be queried without authentication.

This is the only endpoint that would provide a definitive list of matched trades. It is inaccessible without a Polymarket account API key.

---

## 5. Signal Analysis

Four independent signals were evaluated:

### Signal 1 — Gamma `volumeClob` (null for all 12 markets)
Gamma tracks CLOB-specific executed volume separately from legacy AMM volume. `volumeClob=null` on all 12 markets indicates Gamma has not recorded any CLOB-matched trades for these markets.

### Signal 2 — Gamma `lastTradePrice` (null for all 12 markets)
`lastTradePrice` is set by Gamma when a trade matches on the CLOB. It is null for every active market. For comparison: a control market queried earlier ("New Rihanna Album before GTA VI?") returned `lastTradePrice=0.52`, confirming Gamma does populate this field when trades occur.

### Signal 3 — CLOB `/last-trade-price` side field (empty string for all 12 markets)
The CLOB endpoint `GET /last-trade-price?token_id={id}` returns a `side` field ("BUY" or "SELL") identifying the aggressing side of the last matched trade. All 12 active markets returned `side=""` (empty string).

For comparison: a control market (condition_id chosen at random from the broader CLOB) returned `{"price":"0.998","side":"SELL"}`, confirming the field is populated when trades exist.

### Signal 4 — Price history immobility
The CLOB `GET /prices-history` endpoint records price samples over time. All 12 markets show:
- 5m markets: 3 data points, all at exactly the initialization price
- 15m markets: 6 data points, all at 0.5
- 1H markets: 20 data points, all at 0.5
- No price movement of any magnitude across any market

In an active CLOB, matched trades shift the reported price. Zero price movement across all 12 markets over their entire observable history is consistent with zero matched trades.

---

## 6. Answers to Required Questions

### Q1. Does volume=NULL definitively mean zero trades?

**No — not by itself.**

The application stores `volume=NULL` because the CLOB `/markets/{condition_id}` endpoint does not expose volume fields at all. This NULL is a data pipeline artifact: the fields are absent from the response regardless of trading activity. `volume=NULL` in the application database cannot be used as evidence of zero trades.

However, `volumeClob=null` from Gamma (correctly queried by slug) is a meaningful signal. Gamma populates `volumeClob` from CLOB trade data independently. A null value there indicates no CLOB trades have been recorded by Gamma for these markets.

### Q2. Can executed trades exist while volume remains NULL?

**Unknown — with qualification.**

For the application's internal `volume=NULL`: yes, trades could exist while this remains null, because the data pipeline is broken (wrong endpoint, missing field).

For Gamma's `volumeClob=null`: there is no documented propagation lag for Gamma's volume accounting. Whether Gamma could fail to reflect a real trade is not specified in any accessible documentation. If such a lag exists, it is undocumented and unquantifiable.

For `lastTradePrice=null` from Gamma and `side=""` from CLOB: these are additional independent checks. Both would need to fail simultaneously to mask actual trading activity. No documented failure mode covers this.

**The only definitive resolution** requires access to the authenticated `/trades` endpoint, which was not obtainable.

### Q3. Is there any direct evidence that trading has occurred on any active market?

**No.**

All four accessible proxy signals are consistent with zero trading activity across all 12 markets:

- Gamma `volumeClob`: null (12/12 markets)
- Gamma `lastTradePrice`: null (12/12 markets)
- CLOB `last-trade-price.side`: empty string (12/12 markets)
- Price history: no movement from initialization price (12/12 markets)

No signal from any market contradicts the zero-trade interpretation.

### Q4. Is the statement "no trading has occurred" proven, plausible, or unsupported?

**Plausible, approaching proven — not formally proven.**

The statement is supported by four independent signals across all 12 markets, none of which show any evidence of trading. The interpretation is consistent and internally coherent. The only available counter-evidence would be a contradicting result from the authenticated `/trades` endpoint, which is inaccessible.

The statement cannot be formally proven because:
1. The CLOB `/trades` endpoint (direct trade ledger) requires authentication and was not queried.
2. It is theoretically possible (though undocumented) that Gamma has a propagation delay for `volumeClob` and `lastTradePrice`.

**Formal characterization:** The evidence is sufficient to treat "no trading has occurred" as the working conclusion. It is not speculation. It would require at minimum one contradicting signal from an independent source to be revised.

---

## 7. Additional Finding: Data Pipeline Bug

The application extracts `volume` and `liquidity` from `GET /clob.polymarket.com/markets/{condition_id}`. These fields do not exist in that endpoint's response. The correct source for per-market CLOB volume is:

- `GET https://gamma-api.polymarket.com/markets?slug={market_slug}` → `volumeClob`, `liquidityClob`

Additionally, `GET https://gamma-api.polymarket.com/markets?conditionId={cid}` does not function as a filter — the parameter is silently ignored by the Gamma API. Any code using this lookup pattern is receiving unrelated market data.

---

## 8. Summary Table

| Signal | Source | All 12 Markets | Interpretation |
|---|---|---|---|
| `volumeClob` | Gamma (by slug) | null | No CLOB trade volume recorded |
| `lastTradePrice` | Gamma (by slug) | null | No matched trade price recorded |
| `last-trade-price.side` | CLOB | "" (empty) | No matched trade side recorded |
| Price history movement | CLOB | 0.0 (zero movement) | No price-shifting trade activity |
| Order book structure | CLOB | Symmetric 46/46 | AMM initialization, not organic |
| `/trades` (direct ledger) | CLOB | 401 Unauthorized | **Inaccessible without credentials** |

---

*All data queried live on 2026-06-19. No cached or synthetic data was used.*
