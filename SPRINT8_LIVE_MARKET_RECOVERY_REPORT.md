# Sprint 8 — Live Market Recovery Investigation

**Date:** 2026-06-18  
**Type:** Research only — no code changes  
**Objective:** Discover where the Polymarket website's live "Up or Down" markets come from and identify why the Universe Engine missed them

---

## Executive Summary

The Universe Engine is broken in two specific ways — **wrong API endpoint** and **wrong field name** for tokens. The Polymarket website is fully live with all 12 series active today. Every series has 20 pre-staged markets with real CLOB liquidity. The fix is surgical:

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| All 240 markets expired | Wrong endpoint: `/events?series_slug=` returns historical; should use `/series?slug=` | Use series endpoint |
| Token IDs all null | Wrong field: looked for `tokens[]` array; field is `clobTokenIds` (JSON string) | Parse `clobTokenIds` |

---

## Task 1 — Data Sources on Polymarket Website

The Polymarket website (`https://polymarket.com/crypto/5M`) is a **Next.js app router** application (no `__NEXT_DATA__` hydration blob). It fetches data dynamically at runtime from the Gamma API and CLOB API.

**Observed network calls the website makes:**
- `GET https://gamma-api.polymarket.com/series?slug={series_slug}` → primary source for the series page
- `GET https://clob.polymarket.com/markets/{conditionId}` → live order book / price data
- `GET https://gamma-api.polymarket.com/events/{event_id}` → full event detail on click

The series endpoint is the single authoritative source. It returns the series metadata plus **20 currently pre-staged events** embedded in the `events[]` array.

---

## Task 2 — All Data Sources Found

### Gamma API

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /series?slug={slug}` | Series + embedded live events | **Primary source. Returns 20 current events.** |
| `GET /events?series_slug={slug}&limit=20` | 20 most recently CREATED events | **What Sprint 7 used. Returns historical 2025 data.** |
| `GET /events?series_slug={slug}&active=true&closed=false` | Open events only | Alternative, also works |
| `GET /events/{event_id}` | Full event + market detail | Used for deep inspection |

### CLOB API

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /markets?active=true` | All active CLOB markets (paginated) | Returns 1000 records per page; no series filter available |
| `GET /markets/{conditionId}` | Single market live prices | For real-time bid/ask |

### Token IDs Field

Token IDs are in the **`clobTokenIds`** field on each market object — a **JSON-encoded string** (not an array):

```
"clobTokenIds": "[\"89914745...\", \"54523562...\"]"
```

- Index 0 → **YES token**
- Index 1 → **NO token**

Sprint 7's `_extract_tokens()` looked for a `tokens` array of `{token_id, outcome}` objects. That structure does not exist in the Gamma API response. The correct field is `clobTokenIds`.

---

## Task 3 — BTC 5M Current Live Market

**Source:** `GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-5m`  
**Event detail:** `GET https://gamma-api.polymarket.com/events/606380`

| Field | Value |
|-------|-------|
| asset | BTC |
| timeframe | 5m |
| series_slug | `btc-up-or-down-5m` |
| series_id | 10684 |
| event_id | **606380** |
| question | Bitcoin Up or Down - June 18, 6:40PM-6:45PM ET |
| condition_id | `0x81326c52f1df0c6ae70b553dc84b3ef6ae7b5769dd086a4046aa864d71545d15` |
| yes_token_id | `89914745434197090561768660642928718885215370230365649728388341572530801712855` |
| no_token_id | `54523562982062900990767835060308686008217934365568088060293219956372385944551` |
| start_time | 2026-06-17T22:48:07Z |
| end_time | 2026-06-18T22:45:00Z |
| status | **active** (`active=true`, `closed=false`, `acceptingOrders=true`) |
| enableOrderBook | true |
| liquidity (CLOB) | $9,105.63 |

**Raw `clobTokenIds` field from API:**
```json
"clobTokenIds": "[\"89914745434197090561768660642928718885215370230365649728388341572530801712855\", \"54523562982062900990767835060308686008217934365568088060293219956372385944551\"]"
```

---

## Task 4 — ETH / SOL / XRP 5M Current Live Markets

### ETH 5M

**Source:** `GET https://gamma-api.polymarket.com/events/606359`

| Field | Value |
|-------|-------|
| asset | ETH |
| timeframe | 5m |
| series_slug | `eth-up-or-down-5m` |
| series_id | 10683 |
| event_id | **606359** |
| question | Ethereum Up or Down - June 18, 6:30PM-6:35PM ET |
| condition_id | `0x1e23a94f8b1cf083b96b3e7b7b04aba06dc89f5fa5f6f1288eb199d8819370bb` |
| yes_token_id | `6182344816968956186585494988627514504059134004328842464582869029041084339881` |
| no_token_id | `85247021204357004402851374924567591391430636184000293779215004295635484319415` |
| start_time | 2026-06-17T22:39:35Z |
| end_time | 2026-06-18T22:35:00Z |
| status | **active** (`acceptingOrders=true`) |

---

### SOL 5M

**Source:** `GET https://gamma-api.polymarket.com/events/606393`

| Field | Value |
|-------|-------|
| asset | SOL |
| timeframe | 5m |
| series_slug | `sol-up-or-down-5m` |
| series_id | 10686 |
| event_id | **606393** |
| question | Solana Up or Down - June 18, 6:45PM-6:50PM ET |
| condition_id | `0xb0bafb0d1d8bfccc898e27f877774c970772bad991dec397436791c5bcdd4d97` |
| yes_token_id | `102864674700882629861466487364085820233491326744016562412791570427780078615595` |
| no_token_id | `24182082919494996590942907600832889695901538975655168949484222671304264968610` |
| start_time | 2026-06-17T22:55:32Z |
| end_time | 2026-06-18T22:50:00Z |
| status | **active** (`acceptingOrders=true`) |

---

### XRP 5M

**Source:** `GET https://gamma-api.polymarket.com/events/606375`

| Field | Value |
|-------|-------|
| asset | XRP |
| timeframe | 5m |
| series_slug | `xrp-up-or-down-5m` |
| series_id | 10685 |
| event_id | **606375** |
| question | XRP Up or Down - June 18, 6:35PM-6:40PM ET |
| condition_id | `0x219742eb53244a4367e9e991dfdc5b81c68810d8016e3ff4870ab93913838d30` |
| yes_token_id | `101648292611907408242001318910222960579170432618396555835854787433867941859777` |
| no_token_id | `31921092805139867797731067814953132094223594502391696321475825923239281747068` |
| start_time | 2026-06-17T22:45:39Z |
| end_time | 2026-06-18T22:40:00Z |
| status | **active** (`acceptingOrders=true`) |

---

## Current Live Markets — 15M and 1H

### BTC 15M

| Field | Value |
|-------|-------|
| event_id | 606041 |
| question | Bitcoin Up or Down - June 18, 5:15PM-5:30PM ET |
| condition_id | `0x2d161a7740a3a91254073403691b99c25fa853a97da48352057d73fefc35317a` |
| yes_token_id | `27648896188173612548380264036226588457671133665651599976964560743005017308430` |
| no_token_id | `11707294978979862853634015949344023477368552185310962671423787817319709036125` |
| end_time | 2026-06-18T21:30:00Z |
| status | active |

### ETH 15M

| Field | Value |
|-------|-------|
| event_id | 606051 |
| question | Ethereum Up or Down - June 18, 5:15PM-5:30PM ET |
| condition_id | `0xd1592a5ae6ff9b6e641c47741af7b132ca70f548809af4f87bd9ae197692d39f` |
| yes_token_id | `88490193618347640702950437829202047194672377895435092752436806862937066658491` |
| no_token_id | `81755573141385902126921123756675753645595499420566923024491866006529390735185` |
| end_time | 2026-06-18T21:30:00Z |
| status | active |

### SOL 15M

| Field | Value |
|-------|-------|
| event_id | 605954 |
| question | Solana Up or Down - June 18, 4:30PM-4:45PM ET |
| condition_id | `0x3aa8cf0fa9c2b95420439cf2c02a33a343cd3d625fcfba526364c47497c2c878` |
| yes_token_id | `33254158011574179215007373241939080650005616915311025197535217164111094149396` |
| no_token_id | `12016951273711171160302812581011761975795283073895396999119126187069029130874` |
| end_time | 2026-06-18T20:45:00Z |
| status | active |

### XRP 15M

| Field | Value |
|-------|-------|
| event_id | 606020 |
| question | XRP Up or Down - June 18, 5:00PM-5:15PM ET |
| condition_id | `0x9cd3b37c026b42e0b053e42f7d65df0b62cfca67c37b7b62277b18f560f40e0a` |
| yes_token_id | `80460104705882566158109955085938137020208828956097325705965590618555629360220` |
| no_token_id | `66511111308948037837892920008424364827010917084516848102737024645488918343036` |
| end_time | 2026-06-18T21:15:00Z |
| status | active |

### BTC 1H

| Field | Value |
|-------|-------|
| event_id | 604966 |
| question | Bitcoin Up or Down - June 19, 10AM ET |
| condition_id | `0x355bddd7b508a9317be34bfcd3639d4f28169228a9093b304de020ed872f774e` |
| yes_token_id | `18505505376122985344164176275191298748836623640208728168530609276951090119979` |
| no_token_id | `24799411800218845118153864591090712129071376378864876575283679988474093075078` |
| end_time | 2026-06-19T15:00:00Z |
| status | active |

### ETH 1H

| Field | Value |
|-------|-------|
| event_id | 604967 |
| question | Ethereum Up or Down - June 19, 10AM ET |
| condition_id | `0x1fd5bbf5152a1a916338f5021c5efe70aeb9722438d7a941648ba94a05ca4379` |
| yes_token_id | `1449293876154942556745295931980150275064849688764716882213854244120608995480` |
| no_token_id | `16341359078228611583481772530241717745135750165458501991781414726056393813966` |
| end_time | 2026-06-19T15:00:00Z |
| status | active |

### SOL 1H

| Field | Value |
|-------|-------|
| event_id | 604808 |
| question | Solana Up or Down - June 19, 9AM ET |
| condition_id | `0xd19a2bf0c8240df473de126b6d61f05fbd74351f211973ae8c0ebb1939a13cd2` |
| yes_token_id | `82580449682195808397523890728493043151978368033906379100220424401357416273752` |
| no_token_id | `53973876357789884549074204362776704090580815906795178782956520491103407874532` |
| end_time | 2026-06-19T14:00:00Z |
| status | active |

### XRP 1H

| Field | Value |
|-------|-------|
| event_id | 604969 |
| question | XRP Up or Down - June 19, 10AM ET |
| condition_id | `0x071d10fb9c7bab96048d68394663cf214ad1662ccd58d089026650808245a194` |
| yes_token_id | `102295327281528030672220804549027032930932979684486798301674437117263437034913` |
| no_token_id | `113378795739794706534099708756200845933479497629497952657402518469214442925891` |
| end_time | 2026-06-19T15:00:00Z |
| status | active |

---

## Task 5 — Are These Markets Discoverable Automatically?

**Yes — fully and reliably.**

The series endpoint is deterministic and stateless. For each of the 12 known series slugs, a single HTTP request returns all 20 currently live markets with full metadata:

```
GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-5m
```

Response contains:
- Series metadata (id, slug, volume24hr, liquidity)
- `events[]` array — 20 currently staged markets, sorted by `endDate`
- Each event has the full `markets[]` array embedded with `conditionId` and `clobTokenIds`

No authentication required. No pagination needed. One call per series = 12 calls total.

---

## Task 6 — Live Website vs Universe Engine Mismatch

### Side-by-Side Comparison: BTC 5M

| Field | Universe Engine DB (Sprint 7) | Live Website (Today) |
|-------|------------------------------|----------------------|
| event_id | 107751 | **606380** |
| question | Bitcoin Up or Down - Dec 18, 3:55AM-4:00AM ET | **Bitcoin Up or Down - June 18, 6:40PM-6:45PM ET** |
| end_time | 2025-12-18T09:00:00Z | **2026-06-18T22:45:00Z** |
| status | expired | **active** |
| condition_id | `0x11dc46...` | **`0x81326c...`** |
| yes_token_id | **null** | **`89914745...`** |
| no_token_id | **null** | **`54523562...`** |
| acceptingOrders | false | **true** |
| liquidity | $0 | **$9,105.63** |

### Root Cause of the Mismatch

**Wrong API endpoint.** Sprint 7 uses:

```
GET /events?series_slug=btc-up-or-down-5m&limit=20
```

This endpoint paginates through ALL historical events ordered by their **creation date**, returning the 20 most recently created. The most recently created events for each series happen to be from December 2025 — the last batch that was bulk-staged before the system started rolling events forward on a per-5-minute cycle.

The Polymarket website uses:

```
GET /series?slug=btc-up-or-down-5m
```

This endpoint returns the **series object** with its currently active/upcoming events embedded in `events[]`. These are the 20 real-time events being traded right now.

### Wrong Token Field

Sprint 7's `_extract_tokens()` tried to iterate a `tokens` list looking for `outcome == "Yes"` / `outcome == "No"` objects. The Gamma API does not use this structure. Instead, each market object has:

```json
"clobTokenIds": "[\"<yes_token_id>\", \"<no_token_id>\"]"
```

This is a **JSON-encoded string** (not a list). Parsing it as JSON gives `[yes_token_id, no_token_id]` where index 0 = YES, index 1 = NO.

---

## Task 7 — Endpoint That Returns the ACTIVE Market Only

**Definition:** The active market is the one currently open for trading — the event with the **earliest future `endDate`** in the series.

**Endpoint:**

```
GET https://gamma-api.polymarket.com/series?slug={series_slug}
```

From the response `events[]`, filter by:
- `active == true`
- `closed == false`

Sort by `endDate` ascending. The **first result** is the currently active market.

**Example (BTC 5m):**
```
GET https://gamma-api.polymarket.com/series?slug=btc-up-or-down-5m

→ events[0] (sorted by endDate ASC):
  event_id: 606380
  endDate: 2026-06-18T22:45:00Z   ← earliest = CURRENT/ACTIVE
  acceptingOrders: true
  conditionId: 0x81326c52f1df0c6ae70b553dc84b3ef6ae7b5769dd086a4046aa864d71545d15
```

**Alternative (events endpoint with filters):**
```
GET https://gamma-api.polymarket.com/events?series_slug={slug}&active=true&closed=false&limit=1&order=endDate&ascending=true
```

---

## Task 8 — Endpoint That Returns the NEXT Market Only

**Definition:** The next market is the one staged after the current active window — the event with the **second earliest future `endDate`**.

**Endpoint:** Same series endpoint, second result:

```
GET https://gamma-api.polymarket.com/series?slug={series_slug}
```

From the response `events[]`, filter by `active=true` and `closed=false`, sort by `endDate` ascending. The **second result** is the next market.

**Example (BTC 5m):**
```
→ events[1] (sorted by endDate ASC):
  event_id: 606397
  endDate: 2026-06-18T22:50:00Z   ← next 5-minute window
  acceptingOrders: true
```

**Pattern:** The series endpoint always pre-stages **20 events ahead**. For 5m markets that means ~100 minutes of pre-staged markets. For 15m it's ~5 hours. For 1H it's ~20 hours.

---

## Full Series — Live Market Status (June 18, 2026)

| Asset | TF | Series Slug | Series ID | Live Events | Liquidity (series) |
|-------|----|-------------|-----------|-------------|-------------------|
| BTC | 5m | `btc-up-or-down-5m` | 10684 | 20 | $2,251,340 |
| ETH | 5m | `eth-up-or-down-5m` | 10683 | 20 | $1,251,702 |
| SOL | 5m | `sol-up-or-down-5m` | 10686 | 20 | $716,896 |
| XRP | 5m | `xrp-up-or-down-5m` | 10685 | 20 | $720,774 |
| BTC | 15m | `btc-up-or-down-15m` | 10192 | 20 | — |
| ETH | 15m | `eth-up-or-down-15m` | 10191 | 20 | — |
| SOL | 15m | `sol-up-or-down-15m` | 10423 | 20 | — |
| XRP | 15m | `xrp-up-or-down-15m` | 10422 | 20 | — |
| BTC | 1H | `btc-up-or-down-hourly` | 10114 | 20 | — |
| ETH | 1H | `eth-up-or-down-hourly` | 10117 | 20 | — |
| SOL | 1H | `solana-up-or-down-hourly` | 10122 | 20 | — |
| XRP | 1H | `xrp-up-or-down-hourly` | 10123 | 20 | — |

All 12 series: **active=true, closed=false**  
Total live pre-staged markets: **240**  
All 240: acceptingOrders=true, enableOrderBook=true, clobTokenIds populated

---

## Findings Summary

### Finding 1 — Series API Endpoint is the Correct Source

The Gamma API has two distinct patterns for fetching events:

| Pattern | Endpoint | Returns | Correct? |
|---------|----------|---------|---------|
| Sprint 7 (WRONG) | `GET /events?series_slug={slug}&limit=20` | 20 most recently *created* events — historical | ❌ |
| Correct | `GET /series?slug={slug}` | Series + 20 currently *live* events | ✅ |

### Finding 2 — Token IDs Are in `clobTokenIds` (Not `tokens`)

| | Sprint 7 Expectation | Actual API Response |
|--|---------------------|---------------------|
| Field name | `tokens` (array of objects) | `clobTokenIds` (JSON string) |
| YES token | `tokens[i].token_id where outcome=="Yes"` | `json.loads(clobTokenIds)[0]` |
| NO token | `tokens[i].token_id where outcome=="No"` | `json.loads(clobTokenIds)[1]` |

### Finding 3 — Markets Are Continuously Pre-Staged

Polymarket stages **20 markets ahead** per series at all times. As each market expires, a new one is automatically added to maintain the 20-event queue. The scheduler that does this is entirely server-side — no special API calls are needed to "unlock" upcoming markets. They appear automatically in the series endpoint.

### Finding 4 — Correct Status Classification

A market from the series endpoint should be classified as:
- **active** = `endDate` is within the current 5m/15m/1H window AND `acceptingOrders=true`
- **upcoming** = `endDate` is in the future AND not the earliest-endDate event
- **expired** = `closed=true` OR `endDate` is in the past

The current `_determine_status()` logic in Sprint 7 is functionally correct — it just never receives current data because the wrong endpoint is called.

---

## Recommended Fixes for Sprint 8

These are findings only — no code written.

1. **Replace `/events?series_slug=` with `/series?slug=`** in `GammaSeriesClient`
   - Call `GET /series?slug={slug}` per series (12 calls total)
   - Parse `response[0]["events"]` to get the 20 live events

2. **Replace `_extract_tokens()` logic** — parse `clobTokenIds` instead of `tokens`
   - `token_ids = json.loads(market["clobTokenIds"])`
   - `yes_token_id = token_ids[0]`
   - `no_token_id = token_ids[1]`

3. **No other changes required** — the DB schema, status logic, scheduler, endpoints, and test harness are all correct
