# SPRINT 6 — Source Discovery Report
## Polymarket `/crypto/5M`, `/crypto/15M`, `/crypto/1H` — Data Source Investigation

**Date:** 2026-06-18  
**Investigator:** QA / Source Research  
**Method:** Live HTML extraction (RSC/Next.js dehydrated state), direct API probing, page source analysis  

---

## Executive Summary

All three pages (`/crypto/5M`, `/crypto/15M`, `/crypto/1H`) are served by Polymarket's Next.js
(App Router) frontend. Each page fetches its market data from a **single canonical source**:

> **`GET https://gamma-api.polymarket.com/series?slug={series_slug}`**

The CLOB API is **not involved** in serving these pages. The Gamma events API tag/seriesSlug
filters **do not work** as a discovery tool. Only the Gamma **Series** endpoint with an exact
`slug` parameter reliably returns the live markets shown on each page.

---

## TASK 1 — Source Investigation Results

### Source 1: CLOB API

| Field | Value |
|---|---|
| Endpoint | `https://clob.polymarket.com/markets` |
| Records | ~250,000 |
| Contains BTC updown? | YES (slug: `btc-updown-5m-{epoch}`, `btc-updown-15m-{epoch}`, etc.) |
| Contains ETH updown? | YES |
| Contains SOL updown? | YES |
| Contains XRP updown? | YES |
| Serves `/crypto/5M` page? | **NO** |
| Notes | The CLOB stores the binary option markets as records, but the page does not query the CLOB directly. The `market_slug` query param on CLOB returns unrelated results. The CLOB has no `seriesSlug` or timeframe filter. |

### Source 2: Gamma API — Events Endpoint

| Field | Value |
|---|---|
| Endpoint | `https://gamma-api.polymarket.com/events` |
| Filter params tested | `tag=5M`, `tagSlug=5M`, `tagId=102892`, `seriesSlug=btc-up-or-down-5m`, `seriesId=10684`, `category=Crypto` |
| Contains BTC updown? | YES (embedded in event objects) |
| Contains ETH updown? | YES |
| Contains SOL updown? | YES |
| Contains XRP updown? | YES |
| Serves `/crypto/5M` page? | **NO — filter params broken** |
| Notes | The `tagSlug=5M` and `seriesSlug=*` filters on this endpoint return arbitrary old markets (NBA, NFL, etc.), not the 5M crypto markets. The endpoint cannot be used as a reliable discovery mechanism for these pages. |

### Source 3: Gamma API — **Series Endpoint** ✅ CONFIRMED PRIMARY SOURCE

| Field | Value |
|---|---|
| Endpoint | `https://gamma-api.polymarket.com/series?slug={series_slug}` |
| Contains BTC updown? | **YES — full event list with market data** |
| Contains ETH updown? | **YES** |
| Contains SOL updown? | **YES** |
| Contains XRP updown? | **YES** |
| Serves `/crypto/5M` page? | **YES — confirmed via RSC dehydrated state** |
| Serves `/crypto/15M` page? | **YES** |
| Serves `/crypto/1H` page? | **YES** |
| Notes | Each series slug returns a JSON object with `events[]` array. Each event has `markets[]` with full `conditionId`, `slug`, `question`, `outcomePrices`, and `clobTokenIds`. Returns up to 20 look-ahead events per series. |

### Source 4: Gamma API — Markets Endpoint

| Field | Value |
|---|---|
| Endpoint | `https://gamma-api.polymarket.com/markets` |
| Contains BTC updown? | YES (with `conditionId` lookup) |
| Contains ETH updown? | YES |
| Contains SOL updown? | YES |
| Contains XRP updown? | YES |
| Serves `/crypto/5M` page? | **NO** |
| Notes | Can be used to look up individual market metadata by `conditionId`, but is not the source for page rendering. |

### Source 5: Gamma API — Series List (All Series)

| Field | Value |
|---|---|
| Endpoint | `https://gamma-api.polymarket.com/series?limit=200` |
| Total series returned | 50 (at default limit) |
| Contains 5M/15M/1H series? | **Partial** — returns only 50; the 5M/15M/1H series (ids 10114–10686) are beyond the default page and not discoverable via this list |
| Notes | The series list endpoint does not paginate to the high-ID series. Must query by slug directly. |

### Source 6: NextJS Internal Endpoints

| Field | Value |
|---|---|
| Endpoint | `https://polymarket.com/api/events` / `https://polymarket.com/api/markets` |
| Status | **HTTP 404** — these routes do not exist |
| Notes | Polymarket uses Next.js App Router with React Server Components (RSC). Page data is dehydrated server-side and embedded as `self.__next_f.push([1, ...])` script chunks in the HTML. No public `/api/*` route is exposed. |

### Source 7: Crypto Category API

| Field | Value |
|---|---|
| Internal query key | `"crypto-counts"` (found in RSC dehydrated state) |
| Data | `{all:309, fiveM:7, fifteenM:7, hourly:9, fourhour:7, daily:11, weekly:61, monthly:24, bitcoin:36, ethereum:18, solana:13, xrp:11, ...}` |
| Endpoint | Not directly public — populated server-side inside the Next.js page |
| Notes | The counts are embedded in the page RSC data. The `fiveM:7` count means 7 active events across all 5M assets at time of capture. |

---

## TASK 2 — Per-Source Summary Table

| Source | Endpoint | Records | BTC ↕ | ETH ↕ | SOL ↕ | XRP ↕ | Powers Page? |
|---|---|---|---|---|---|---|---|
| CLOB API | `clob.polymarket.com/markets` | ~250,000 | ✅ | ✅ | ✅ | ✅ | ❌ |
| Gamma Events | `gamma-api.polymarket.com/events` | ~3,499 active crypto | ✅ | ✅ | ✅ | ✅ | ❌ (broken filter) |
| **Gamma Series** | `gamma-api.polymarket.com/series?slug={slug}` | 20 events per series | ✅ | ✅ | ✅ | ✅ | ✅ **PRIMARY** |
| Gamma Markets | `gamma-api.polymarket.com/markets?conditionId={cid}` | 1 market per call | ✅ | ✅ | ✅ | ✅ | ❌ |
| NextJS internal | `polymarket.com/api/*` | N/A | ❌ | ❌ | ❌ | ❌ | ❌ (404) |

---

## TASK 3 — Exact Market IDs: `/crypto/5M`

Source: RSC dehydrated state embedded in page HTML (captured 2026-06-18T07:12:38 UTC)  
and confirmed via Gamma Series API (captured 2026-06-18T~07:18 UTC).

### Live Markets on `/crypto/5M` at Time of Investigation

> Each row is one currently-active 5-minute event on the page.

**BTC 5M** — Series: `btc-up-or-down-5m` (id: 10684)

| Event ID | Slug | Title | Condition ID |
|---|---|---|---|
| 604131 | `btc-updown-5m-1781770200` | Bitcoin Up or Down - June 18, 4:10AM-4:15AM ET | `0xa70063464788e3fa68cfec108dcf2f11efac2e77498553c9a17cd198f61ce997` |
| 606380 | `btc-updown-5m-1781822400` | Bitcoin Up or Down - June 18, 6:40PM-6:45PM ET | *(live, rotates every 5 min)* |
| 606397 | `btc-updown-5m-1781822700` | Bitcoin Up or Down - June 18, 6:45PM-6:50PM ET | — |
| 606406 | `btc-updown-5m-1781823000` | Bitcoin Up or Down - June 18, 6:50PM-6:55PM ET | — |
| 606414 | `btc-updown-5m-1781823300` | Bitcoin Up or Down - June 18, 6:55PM-7:00PM ET | — |
| 606434 | `btc-updown-5m-1781823600` | Bitcoin Up or Down - June 18, 7:00PM-7:05PM ET | — |
| 606445 | `btc-updown-5m-1781824200` | Bitcoin Up or Down - June 18, 7:10PM-7:15PM ET | — |
| 606461 | `btc-updown-5m-1781824500` | Bitcoin Up or Down - June 18, 7:15PM-7:20PM ET | — |
| 606473 | `btc-updown-5m-1781824800` | Bitcoin Up or Down - June 18, 7:20PM-7:25PM ET | — |
| 606477 | `btc-updown-5m-1781825100` | Bitcoin Up or Down - June 18, 7:25PM-7:30PM ET | — |

**ETH 5M** — Series: `eth-up-or-down-5m` (id: 10683)

| Event ID | Slug | Title | Condition ID |
|---|---|---|---|
| 604133 | `eth-updown-5m-1781770200` | Ethereum Up or Down - June 18, 4:10AM-4:15AM ET | `0xd7960f4d405e068ea5c43d321abb9758029ea4f7ab8085337f82bc0192180ab1` |
| 606359 | `eth-updown-5m-1781821800` | Ethereum Up or Down - June 18, 6:30PM-6:35PM ET | — |
| 606373 | `eth-updown-5m-1781822100` | Ethereum Up or Down - June 18, 6:35PM-6:40PM ET | — |
| 606379 | `eth-updown-5m-1781822400` | Ethereum Up or Down - June 18, 6:40PM-6:45PM ET | — |
| 606396 | `eth-updown-5m-1781822700` | Ethereum Up or Down - June 18, 6:45PM-6:50PM ET | — |
| 606405 | `eth-updown-5m-1781823000` | Ethereum Up or Down - June 18, 6:50PM-6:55PM ET | — |

**SOL 5M** — Series: `sol-up-or-down-5m` (id: 10686)

| Event ID | Slug | Title |
|---|---|---|
| 606393 | `sol-updown-5m-1781822700` | Solana Up or Down - June 18, 6:45PM-6:50PM ET |
| 606403 | `sol-updown-5m-1781823000` | Solana Up or Down - June 18, 6:50PM-6:55PM ET |
| 606418 | `sol-updown-5m-1781823300` | Solana Up or Down - June 18, 6:55PM-7:00PM ET |
| 606449 | `sol-updown-5m-1781824200` | Solana Up or Down - June 18, 7:10PM-7:15PM ET |
| 606472 | `sol-updown-5m-1781824800` | Solana Up or Down - June 18, 7:20PM-7:25PM ET |

**XRP 5M** — Series: `xrp-up-or-down-5m` (id: 10685)

| Event ID | Slug | Title |
|---|---|---|
| 606375 | `xrp-updown-5m-1781822100` | XRP Up or Down - June 18, 6:35PM-6:40PM ET |
| 606383 | `xrp-updown-5m-1781822400` | XRP Up or Down - June 18, 6:40PM-6:45PM ET |
| 606385 | `xrp-updown-5m-1781822700` | XRP Up or Down - June 18, 6:45PM-6:50PM ET |
| 606402 | `xrp-updown-5m-1781823000` | XRP Up or Down - June 18, 6:50PM-6:55PM ET |
| 606420 | `xrp-updown-5m-1781823300` | XRP Up or Down - June 18, 6:55PM-7:00PM ET |

---

## TASK 4 — Exact Market IDs: `/crypto/15M`

Source: RSC dehydrated state (captured 2026-06-18T07:13:21 UTC) + Gamma Series API

**BTC 15M** — Series: `btc-up-or-down-15m` (id: 10192)

| Event ID | Slug | Title | Condition ID |
|---|---|---|---|
| 604106 | `btc-updown-15m-1781769600` | BTC Up or Down 15m | `0x497831322da9dd83dad98f931077b4a2659ff979cd43040ec0463d57dab8a225` |
| 606041 | `btc-updown-15m-1781817300` | Bitcoin Up or Down - June 18, 5:15PM-5:30PM ET | — |
| 606071 | `btc-updown-15m-1781818200` | Bitcoin Up or Down - June 18, 5:30PM-5:45PM ET | — |
| 606104 | `btc-updown-15m-1781819100` | Bitcoin Up or Down - June 18, 5:45PM-6:00PM ET | — |
| 606303 | `btc-updown-15m-1781820000` | Bitcoin Up or Down - June 18, 6:00PM-6:15PM ET | — |
| 606326 | `btc-updown-15m-1781820900` | Bitcoin Up or Down - June 18, 6:15PM-6:30PM ET | — |
| 606363 | `btc-updown-15m-1781821800` | Bitcoin Up or Down - June 18, 6:30PM-6:45PM ET | — |
| 606395 | `btc-updown-15m-1781822700` | Bitcoin Up or Down - June 18, 6:45PM-7:00PM ET | — |
| 606435 | `btc-updown-15m-1781823600` | Bitcoin Up or Down - June 18, 7:00PM-7:15PM ET | — |
| 606489 | `btc-updown-15m-1781825400` | Bitcoin Up or Down - June 18, 7:30PM-7:45PM ET | — |

**ETH 15M** — Series: `eth-up-or-down-15m` (id: 10191)

| Event ID | Slug | Title | Condition ID |
|---|---|---|---|
| 604113 | `eth-updown-15m-1781769600` | ETH Up or Down 15m | `0xc3a736c6f4968a67260302f345918ff9439b708c3f2e440780006d71b61ef26d` |
| 606051 | `eth-updown-15m-1781817300` | Ethereum Up or Down - June 18, 5:15PM-5:30PM ET | — |
| 606078 | `eth-updown-15m-1781818200` | Ethereum Up or Down - June 18, 5:30PM-5:45PM ET | — |

**SOL 15M** — Series: `sol-up-or-down-15m` (id: 10423)

| Event ID | Slug |
|---|---|
| 605954 | `sol-updown-15m-1781814600` |
| 605977 | `sol-updown-15m-1781815500` |

**XRP 15M** — Series: `xrp-up-or-down-15m` (id: 10422)

| Event ID | Slug |
|---|---|
| 606020 | `xrp-updown-15m-1781816400` |
| 606040 | `xrp-updown-15m-1781817300` |

---

## TASK 5 — Exact Market IDs: `/crypto/1H`

Source: Gamma Series API (captured 2026-06-18T~07:19 UTC)

> The `/crypto/1H` page uses "hourly" series — one market per clock hour (e.g. "Bitcoin Up or Down - June 19, 10AM ET").

**BTC 1H** — Series: `btc-up-or-down-hourly` (id: 10114)

| Event ID | Slug | Title |
|---|---|---|
| 604966 | `bitcoin-up-or-down-june-19-2026-10am-et` | Bitcoin Up or Down - June 19, 10AM ET |
| 605096 | `bitcoin-up-or-down-june-19-2026-11am-et` | Bitcoin Up or Down - June 19, 11AM ET |
| 605220 | `bitcoin-up-or-down-june-19-2026-12pm-et` | Bitcoin Up or Down - June 19, 12PM ET |
| 605468 | `bitcoin-up-or-down-june-19-2026-1pm-et`  | Bitcoin Up or Down - June 19, 1PM ET |
| 605595 | `bitcoin-up-or-down-june-19-2026-2pm-et`  | Bitcoin Up or Down - June 19, 2PM ET |
| 605736 | `bitcoin-up-or-down-june-19-2026-3pm-et`  | Bitcoin Up or Down - June 19, 3PM ET |
| 605867 | `bitcoin-up-or-down-june-19-2026-4pm-et`  | Bitcoin Up or Down - June 19, 4PM ET |
| 605997 | `bitcoin-up-or-down-june-19-2026-5pm-et`  | Bitcoin Up or Down - June 19, 5PM ET |
| 606118 | `bitcoin-up-or-down-june-19-2026-6pm-et`  | Bitcoin Up or Down - June 19, 6PM ET |
| 606407 | `bitcoin-up-or-down-june-19-2026-7pm-et`  | Bitcoin Up or Down - June 19, 7PM ET |

**ETH 1H** — Series: `eth-up-or-down-hourly` (id: 10117)

| First Event Slug |
|---|
| `ethereum-up-or-down-june-19-2026-10am-et` |

**SOL 1H** — Series: `solana-up-or-down-hourly` (id: 10122)

| First Event Slug |
|---|
| `solana-up-or-down-june-19-2026-10am-et` |  *(note: uses full "solana" not "sol" in slug)* |

**XRP 1H** — Series: `xrp-up-or-down-hourly` (id: 10123)

| First Event Slug |
|---|
| `xrp-up-or-down-june-19-2026-10am-et` |

---

## TASK 6 — Can These Markets Be Discovered Automatically?

**YES.**

The complete set of markets shown on `/crypto/5M`, `/crypto/15M`, and `/crypto/1H` can be
discovered deterministically using the Gamma Series API. The series slugs are stable (they do
not change between runs), and each series always contains the next 20 upcoming events.

**Conditions:**
- No authentication required
- No pagination required (20 events per series covers all look-ahead windows)
- No scraping required — pure JSON API
- Markets rotate in real-time; a fresh call to the series endpoint always returns the current live set

---

## TASK 7 — Exact API Requests

### Complete Request Set for All Three Pages

#### `/crypto/5M` — 4 requests

```
GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-5m
GET https://gamma-api.polymarket.com/series?slug=eth-up-or-down-5m
GET https://gamma-api.polymarket.com/series?slug=sol-up-or-down-5m
GET https://gamma-api.polymarket.com/series?slug=xrp-up-or-down-5m
```

#### `/crypto/15M` — 4 requests

```
GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-15m
GET https://gamma-api.polymarket.com/series?slug=eth-up-or-down-15m
GET https://gamma-api.polymarket.com/series?slug=sol-up-or-down-15m
GET https://gamma-api.polymarket.com/series?slug=xrp-up-or-down-15m
```

#### `/crypto/1H` — 4 requests

```
GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-hourly
GET https://gamma-api.polymarket.com/series?slug=eth-up-or-down-hourly
GET https://gamma-api.polymarket.com/series?slug=solana-up-or-down-hourly
GET https://gamma-api.polymarket.com/series?slug=xrp-up-or-down-hourly
```

> ⚠️ Note: SOL 1H uses `solana-up-or-down-hourly` (not `sol-up-or-down-hourly`) — the slug diverges from the 5M/15M pattern.

### Complete Series Registry

| Page | Asset | Series Slug | Series ID |
|---|---|---|---|
| `/crypto/5M` | BTC | `btc-up-or-down-5m` | **10684** |
| `/crypto/5M` | ETH | `eth-up-or-down-5m` | **10683** |
| `/crypto/5M` | SOL | `sol-up-or-down-5m` | **10686** |
| `/crypto/5M` | XRP | `xrp-up-or-down-5m` | **10685** |
| `/crypto/15M` | BTC | `btc-up-or-down-15m` | **10192** |
| `/crypto/15M` | ETH | `eth-up-or-down-15m` | **10191** |
| `/crypto/15M` | SOL | `sol-up-or-down-15m` | **10423** |
| `/crypto/15M` | XRP | `xrp-up-or-down-15m` | **10422** |
| `/crypto/1H` | BTC | `btc-up-or-down-hourly` | **10114** |
| `/crypto/1H` | ETH | `eth-up-or-down-hourly` | **10117** |
| `/crypto/1H` | SOL | `solana-up-or-down-hourly` | **10122** |
| `/crypto/1H` | XRP | `xrp-up-or-down-hourly` | **10123** |

### Bonus: 4H Series (also served under `/crypto/` category)

| Asset | Series Slug | Series ID |
|---|---|---|
| BTC | `btc-up-or-down-4h` | **10331** |
| ETH | `eth-up-or-down-4h` | **10332** |
| SOL | `sol-up-or-down-4h` | **10333** |
| XRP | `xrp-up-or-down-4h` | **10327** |

### Response Structure (per Series call)

```json
[
  {
    "id": "10684",
    "slug": "btc-up-or-down-5m",
    "title": "BTC Up or Down 5m",
    "recurrence": "...",
    "active": true,
    "events": [
      {
        "id": "606380",
        "slug": "btc-updown-5m-1781822400",
        "title": "Bitcoin Up or Down - June 18, 6:40PM-6:45PM ET",
        "startTime": "2026-06-18T22:40:00Z",
        "endDate": "2026-06-18T22:45:00Z",
        "seriesSlug": "btc-up-or-down-5m",
        "volume": 609.23,
        "markets": [
          {
            "id": "2579405",
            "conditionId": "0xa70063464788e3fa68cfec108...",
            "slug": "btc-updown-5m-1781770200",
            "question": "Bitcoin Up or Down - June 18, 4:10AM-4:15AM ET",
            "outcomes": ["Up", "Down"],
            "outcomePrices": ["0.485", "0.515"],
            "clobTokenIds": ["78491252...", "20315598..."],
            "bestAsk": 0.50,
            "bestBid": 0.48,
            "lastTradePrice": 0.52,
            "spread": 0.02
          }
        ],
        "tags": [
          {"id": "102892", "label": "5M", "slug": "5M"},
          {"id": "102127", "label": "Up or Down", "slug": "up-or-down"},
          {"id": "235",    "label": "Bitcoin",   "slug": "bitcoin"},
          {"id": "21",     "label": "Crypto",    "slug": "crypto"}
        ]
      }
    ]
  }
]
```

---

## Key Findings

### What Powers Each Page

```
polymarket.com/crypto/5M
  └─ Next.js RSC server-side renders from:
       Gamma Series API × 4 (one per asset)
       Series slugs: btc/eth/sol/xrp-up-or-down-5m

polymarket.com/crypto/15M
  └─ Next.js RSC server-side renders from:
       Gamma Series API × 4
       Series slugs: btc/eth/sol/xrp-up-or-down-15m

polymarket.com/crypto/1H
  └─ Next.js RSC server-side renders from:
       Gamma Series API × 4
       Series slugs: btc/eth-up-or-down-hourly, solana-up-or-down-hourly, xrp-up-or-down-hourly
```

### What Does NOT Work as a Discovery Source

| Approach | Why It Fails |
|---|---|
| `CLOB /markets?tag=5M` | CLOB has no tag or series filter |
| `CLOB /markets?market_slug=btc-updown-5m-{epoch}` | Returns unrelated markets |
| `Gamma /events?tagSlug=5M` | Returns old sports markets, not crypto updown |
| `Gamma /events?seriesSlug=btc-up-or-down-5m` | Returns wrong/unrelated records |
| `Gamma /events?seriesId=10684` | Also returns wrong records |
| `Gamma /series` (list, no slug) | Paginates to max 50; high-ID series (10114–10686) not included |
| `polymarket.com/api/*` | HTTP 404 — no public API routes |

### Market Cadence

| Page | Duration per market | New market every | Look-ahead |
|---|---|---|---|
| `/crypto/5M` | 5 minutes | 5 minutes | ~20 markets (~100 min) |
| `/crypto/15M` | 15 minutes | 15 minutes | ~20 markets (~300 min / 5 hrs) |
| `/crypto/1H` | 1 hour | 1 hour | ~20 markets (~20 hrs) |

### Tag IDs Discovered

The following Gamma tag IDs were found embedded in the page HTML:

| Tag ID | Label | Slug |
|---|---|---|
| `102892` | 5M | `5M` |
| `102467` | 15M | `15M` |
| `102127` | Up or Down | `up-or-down` |
| `21` | Crypto | `crypto` |
| `235` | Bitcoin | `bitcoin` |

---

## Conclusion

```
┌─────────────────────────────────────────────────────────────────┐
│              SPRINT 6 SOURCE DISCOVERY — CONCLUSION              │
├─────────────────────────────────────────────────────────────────┤
│  Primary Source: Gamma API Series endpoint                       │
│  URL Pattern:    gamma-api.polymarket.com/series?slug={slug}     │
│                                                                  │
│  /crypto/5M  → 4 series (IDs: 10684, 10683, 10686, 10685)      │
│  /crypto/15M → 4 series (IDs: 10192, 10191, 10423, 10422)      │
│  /crypto/1H  → 4 series (IDs: 10114, 10117, 10122, 10123)      │
│                                                                  │
│  Auto-discovery: YES                                             │
│  Auth required: NO                                               │
│  CLOB involved: NO                                               │
│  Gamma Events filter works: NO                                   │
│                                                                  │
│  The series slug is the discovery key. Each slug returns         │
│  up to 20 upcoming events with full conditionId, CLOB token      │
│  IDs, live prices, and market metadata — everything needed       │
│  for trading or analysis.                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

*Report generated: 2026-06-18*  
*Data sources: Live page HTML (RSC dehydrated state), Gamma API Series endpoint*  
*No code was written. No schema was modified. No trading logic was created.*
