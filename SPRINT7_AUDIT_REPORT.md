# Sprint 7 — Market Universe Engine: Audit Report

**Audit Date:** 2026-06-18  
**Auditor:** Live endpoint inspection  
**Endpoints Tested:**
- `GET /api/v1/universe`
- `GET /api/v1/universe/active`
- `GET /api/v1/universe/upcoming`
- `GET /api/v1/universe/stats`

---

## Executive Summary

The Market Universe Engine is **operational and connected to the Gamma API**. All 12 series are being fetched successfully. **240 markets are stored** across the 12 series (20 markets per series). However, three critical issues are identified:

| # | Finding | Severity |
|---|---------|----------|
| 1 | **Zero active markets** — all 240 are `expired` | 🔴 Critical |
| 2 | **Zero upcoming markets** — none scheduled | 🔴 Critical |
| 3 | **Token IDs are null** — `yes_token_id` / `no_token_id` missing for all 240 records | 🟡 High |

---

## Live Stats — `GET /api/v1/universe/stats`

```json
{
  "total": 240,
  "by_status": {
    "active":   0,
    "upcoming": 0,
    "expired":  240
  }
}
```

**By asset and timeframe:**

| Asset | Timeframe | Active | Upcoming | Expired | Total |
|-------|-----------|--------|----------|---------|-------|
| BTC   | 5m        | 0      | 0        | 20      | 20    |
| BTC   | 15m       | 0      | 0        | 20      | 20    |
| BTC   | 1H        | 0      | 0        | 20      | 20    |
| ETH   | 5m        | 0      | 0        | 20      | 20    |
| ETH   | 15m       | 0      | 0        | 20      | 20    |
| ETH   | 1H        | 0      | 0        | 20      | 20    |
| SOL   | 5m        | 0      | 0        | 20      | 20    |
| SOL   | 15m       | 0      | 0        | 20      | 20    |
| SOL   | 1H        | 0      | 0        | 20      | 20    |
| XRP   | 5m        | 0      | 0        | 20      | 20    |
| XRP   | 15m       | 0      | 0        | 20      | 20    |
| XRP   | 1H        | 0      | 0        | 20      | 20    |
| **TOTAL** |       | **0**  | **0**    | **240** | **240** |

---

## Active Markets — `GET /api/v1/universe/active`

**Result: `[]` — Empty list. Zero active markets.**

---

## Upcoming Markets — `GET /api/v1/universe/upcoming`

**Result: `[]` — Empty list. Zero upcoming markets.**

---

## Full Universe Sample — Per Series (`GET /api/v1/universe`)

One representative record shown per series (the most recent `end_time`).

---

### BTC — 5m
**Series slug:** `btc-up-or-down-5m`

| Field         | Value |
|---------------|-------|
| asset         | BTC |
| timeframe     | 5m |
| series_slug   | btc-up-or-down-5m |
| series_id     | 10684 |
| event_id      | 107751 |
| condition_id  | `0x11dc46265dcb11d2a28376ffc192a897c41bfd697163b3cb6d22e4ff5cbfd6e2` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Bitcoin Up or Down - December 18, 3:55AM-4:00AM ET |
| start_time    | 2025-12-17T20:43:52Z |
| end_time      | 2025-12-18T09:00:00Z |
| status        | **expired** |

---

### BTC — 15m
**Series slug:** `btc-up-or-down-15m`

| Field         | Value |
|---------------|-------|
| asset         | BTC |
| timeframe     | 15m |
| series_slug   | btc-up-or-down-15m |
| series_id     | 10192 |
| event_id      | 43967 |
| condition_id  | `0x305e3926c2f260484f665287f66335825d983176b8a055d8cfe423a737068e76` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Bitcoin Up or Down - September 13, 1:30AM-1:45AM ET |
| start_time    | 2025-09-13T02:32:16Z |
| end_time      | 2025-09-13T05:45:00Z |
| status        | **expired** |

---

### BTC — 1H
**Series slug:** `btc-up-or-down-hourly`

| Field         | Value |
|---------------|-------|
| asset         | BTC |
| timeframe     | 1H |
| series_slug   | btc-up-or-down-hourly |
| series_id     | 10114 |
| event_id      | 26613 |
| condition_id  | `0xed204999e5f618f245544926040b97a5bd074348cf04e5e83a1953f9d4f0823e` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Bitcoin Up or Down - June 13, 10 PM ET |
| start_time    | 2025-06-11T11:14:40Z |
| end_time      | 2025-06-14T03:00:00Z |
| status        | **expired** |

---

### ETH — 5m
**Series slug:** `eth-up-or-down-5m`

| Field         | Value |
|---------------|-------|
| asset         | ETH |
| timeframe     | 5m |
| series_slug   | eth-up-or-down-5m |
| series_id     | 10683 |
| event_id      | 107774 |
| condition_id  | `0xc7df0f91329a0d38dac8d4b2a93bbebbb119770d8ae4506712ac9b71f8b0f2b2` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Ethereum Up or Down - December 18, 3:45AM-3:50AM ET |
| start_time    | 2025-12-17T20:43:56Z |
| end_time      | 2025-12-18T08:50:00Z |
| status        | **expired** |

---

### ETH — 15m
**Series slug:** `eth-up-or-down-15m`

| Field         | Value |
|---------------|-------|
| asset         | ETH |
| timeframe     | 15m |
| series_slug   | eth-up-or-down-15m |
| series_id     | 10191 |
| event_id      | 43966 |
| condition_id  | `0x2d7731dd68c6fc250393210169bec6bbb8caac3a9995c444b8ab0e2b07ca58bb` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Ethereum Up or Down - September 13, 1:30AM-1:45AM ET |
| start_time    | 2025-09-13T02:32:16Z |
| end_time      | 2025-09-13T05:45:00Z |
| status        | **expired** |

---

### ETH — 1H
**Series slug:** `eth-up-or-down-hourly`

| Field         | Value |
|---------------|-------|
| asset         | ETH |
| timeframe     | 1H |
| series_slug   | eth-up-or-down-hourly |
| series_id     | 10117 |
| event_id      | 26575 |
| condition_id  | `0x15d7cbdbe309448f0129ea44810140841a0f4f8aa7a67ad725110d1ad9188da4` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Ethereum Up or Down - June 12, 11 PM ET |
| start_time    | 2025-06-10T11:54:38Z |
| end_time      | 2025-06-13T04:00:00Z |
| status        | **expired** |

---

### SOL — 5m
**Series slug:** `sol-up-or-down-5m`

| Field         | Value |
|---------------|-------|
| asset         | SOL |
| timeframe     | 5m |
| series_slug   | sol-up-or-down-5m |
| series_id     | 10686 |
| event_id      | 107777 |
| condition_id  | `0x651026c9632b22d258e18edd1aa13cc6c6dc44300689de56df6fb5bd49b89081` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Solana Up or Down - December 18, 3:40AM-3:45AM ET |
| start_time    | 2025-12-17T20:43:57Z |
| end_time      | 2025-12-18T08:45:00Z |
| status        | **expired** |

---

### SOL — 15m
**Series slug:** `sol-up-or-down-15m`

| Field         | Value |
|---------------|-------|
| asset         | SOL |
| timeframe     | 15m |
| series_slug   | sol-up-or-down-15m |
| series_id     | 10423 |
| event_id      | 66515 |
| condition_id  | `0xe55556ee31e536a10863b996a020a057aed272dc10b30fa36c0042a918f7c00b` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Solana Up or Down - October 27, 8:00PM-8:15PM ET |
| start_time    | 2025-10-27T21:04:06Z |
| end_time      | 2025-10-28T00:15:00Z |
| status        | **expired** |

---

### SOL — 1H
**Series slug:** `solana-up-or-down-hourly`

| Field         | Value |
|---------------|-------|
| asset         | SOL |
| timeframe     | 1H |
| series_slug   | solana-up-or-down-hourly |
| series_id     | 10122 |
| event_id      | 27325 |
| condition_id  | `0xff7a59f36d4088d16dce51bb56dceb34eec7ca3e628374da450b222edf6ea7c4` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | Solana Up or Down - June 18, 11 PM ET |
| start_time    | 2025-06-16T16:32:12Z |
| end_time      | 2025-06-19T04:00:00Z |
| status        | **expired** |

---

### XRP — 5m
**Series slug:** `xrp-up-or-down-5m`

| Field         | Value |
|---------------|-------|
| asset         | XRP |
| timeframe     | 5m |
| series_slug   | xrp-up-or-down-5m |
| series_id     | 10685 |
| event_id      | 107752 |
| condition_id  | `0xda37701fb246dc78713e760cd5a7b115d4a9e5bda63c5cb82be1bedd4d33751d` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | XRP Up or Down - December 18, 3:35AM-3:40AM ET |
| start_time    | 2025-12-17T20:43:52Z |
| end_time      | 2025-12-18T08:40:00Z |
| status        | **expired** |

---

### XRP — 15m
**Series slug:** `xrp-up-or-down-15m`

| Field         | Value |
|---------------|-------|
| asset         | XRP |
| timeframe     | 15m |
| series_slug   | xrp-up-or-down-15m |
| series_id     | 10422 |
| event_id      | 66514 |
| condition_id  | `0x6c247f39f18fc484e272101e934bfd9cf55ec11769ed762c63b0290f8e7c5cc3` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | XRP Up or Down - October 27, 8:00PM-8:15PM ET |
| start_time    | 2025-10-27T21:04:06Z |
| end_time      | 2025-10-28T00:15:00Z |
| status        | **expired** |

---

### XRP — 1H
**Series slug:** `xrp-up-or-down-hourly`

| Field         | Value |
|---------------|-------|
| asset         | XRP |
| timeframe     | 1H |
| series_slug   | xrp-up-or-down-hourly |
| series_id     | 10123 |
| event_id      | 28297 |
| condition_id  | `0xcf2f10a5f6ce3d8923310d33a60038e8d7f4374d6340be81860f27c1e2df7ba4` |
| yes_token_id  | **null** |
| no_token_id   | **null** |
| question      | XRP Up or Down - June 24, 8PM ET |
| start_time    | 2025-06-23T13:19:56Z |
| end_time      | 2025-06-25T01:00:00Z |
| status        | **expired** |

---

## Audit Questions — Answers

### 1. Do all 12 series return active markets?

**NO.**

Zero active markets across all 12 series.

**Root cause:** The Gamma API endpoint `GET /events?series_slug={slug}&limit=20` returns the 20 most recently created events for each series. As of the audit date (2026-06-18), all 20 events returned per series have `end_time` values that are in the past (ranging from June 2025 to December 2025). The `expire_stale_markets()` function correctly marks them all as expired. The Gamma API is not returning any events for 2026.

This indicates one of two things:
- The series have been paused or discontinued on Polymarket since late 2025
- The API pagination direction needs to be reversed (i.e., the API needs to be queried for the *latest/newest* events, not the most recently created ones)

---

### 2. Do all 12 series return upcoming markets?

**NO.**

Zero upcoming markets across all 12 series. Same root cause as Question 1: no future-dated events are returned by the API for any of the 12 series.

---

### 3. Are condition IDs populated?

**YES — fully populated.**

All 240 records have valid condition IDs in the format `0x{64 hex chars}`. Examples:

- BTC 5m: `0x11dc46265dcb11d2a28376ffc192a897c41bfd697163b3cb6d22e4ff5cbfd6e2`
- ETH 1H: `0x15d7cbdbe309448f0129ea44810140841a0f4f8aa7a67ad725110d1ad9188da4`
- XRP 15m: `0x6c247f39f18fc484e272101e934bfd9cf55ec11769ed762c63b0290f8e7c5cc3`

`condition_id` missing: **0 / 240** ✅

---

### 4. Are token IDs populated?

**NO — token IDs are null for all 240 records.**

| Field        | Populated | Null |
|--------------|-----------|------|
| yes_token_id | 0         | 240  |
| no_token_id  | 0         | 240  |

**Root cause:** The Gamma API's `/events` response embeds market objects that do not include a `tokens` array (or return an empty array). The `GammaMarket.tokens` field in `GammaMarketRaw` parses as an empty list, so `_extract_tokens()` finds no YES or NO outcomes and returns `(None, None)` for both token IDs.

The token data may be available via a separate `/markets` endpoint on the Gamma API (e.g., `GET /markets?event_slug={slug}`), rather than being embedded in the event response.

---

### 5. Are expiration times populated?

**YES — fully populated.**

All 240 records have `end_time` set. Examples:

| Series               | Latest end_time             |
|----------------------|-----------------------------|
| BTC 5m               | 2025-12-18T09:00:00Z       |
| BTC 15m              | 2025-09-13T05:45:00Z       |
| BTC 1H               | 2025-06-14T03:00:00Z       |
| ETH 5m               | 2025-12-18T08:50:00Z       |
| ETH 15m              | 2025-09-13T05:45:00Z       |
| ETH 1H               | 2025-06-13T04:00:00Z       |
| SOL 5m               | 2025-12-18T08:45:00Z       |
| SOL 15m              | 2025-10-28T00:15:00Z       |
| SOL 1H               | 2025-06-19T04:00:00Z       |
| XRP 5m               | 2025-12-18T08:40:00Z       |
| XRP 15m              | 2025-10-28T00:15:00Z       |
| XRP 1H               | 2025-06-25T01:00:00Z       |

`end_time` missing: **0 / 240** ✅  
`start_time` missing: **0 / 240** ✅

---

### 6. Any missing fields?

| Field        | Populated | Missing | Status |
|--------------|-----------|---------|--------|
| asset        | 240       | 0       | ✅ OK |
| timeframe    | 240       | 0       | ✅ OK |
| series_slug  | 240       | 0       | ✅ OK |
| series_id    | 240       | 0       | ✅ OK |
| event_id     | 240       | 0       | ✅ OK |
| condition_id | 240       | 0       | ✅ OK |
| question     | 240       | 0       | ✅ OK |
| start_time   | 240       | 0       | ✅ OK |
| end_time     | 240       | 0       | ✅ OK |
| status       | 240       | 0       | ✅ OK |
| created_at   | 240       | 0       | ✅ OK |
| updated_at   | 240       | 0       | ✅ OK |
| yes_token_id | **0**     | **240** | 🔴 MISSING |
| no_token_id  | **0**     | **240** | 🔴 MISSING |

**12 of 14 fields fully populated. 2 fields (token IDs) are null across all records.**

---

## Issue Analysis

### Issue 1 — All Markets Expired (Critical)

**What the Gamma API returns:** 20 historical events per series, all with `end_time` in the past (mid-2025 through late-2025).

**The most recent data per series:**
- BTC/ETH/XRP 5m → most recent events end December 2025
- BTC/ETH 15m → most recent events end September 2025
- SOL/XRP 15m → most recent events end October 2025
- Hourly series → most recent events end June-June 2025

**Today's date:** 2026-06-18. All returned events are 6–12 months in the past.

**Possible explanations:**
1. The series may be **discontinued** — Polymarket stopped creating new events for these series after late 2025
2. The API may require a **sort order parameter** to get the freshest/future events (e.g., `order=asc`, `sort_by=startDate`)
3. The API may require **filtering by active=true** or **closed=false** on the events endpoint

---

### Issue 2 — Token IDs Null (High)

**What happens:** `GammaMarketRaw.tokens` always parses as an empty list from the `/events` response. No YES/NO token entries are found.

**Likely cause:** The Gamma API's event response structure for markets does not include a `tokens` field. Token IDs (CLOB token identifiers) may live on a different endpoint, or under a different field name in the market object (e.g., `clob_token_ids`, `outcomePrices`, or may require a separate `GET /markets/{conditionId}` call).

---

## Data Quality Summary

| Check | Result |
|-------|--------|
| API connectivity (all 12 series) | ✅ Connected |
| Records stored | ✅ 240 (20 per series) |
| Series IDs resolved | ✅ All 12 |
| Event IDs resolved | ✅ All 240 |
| Condition IDs populated | ✅ All 240 |
| Start/end times populated | ✅ All 240 |
| Token IDs populated | ❌ 0/240 |
| Active markets | ❌ 0 |
| Upcoming markets | ❌ 0 |
| Expired markets | ⚠️ 240/240 |
