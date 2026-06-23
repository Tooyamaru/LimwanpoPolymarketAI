# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 05:38:28 UTC
**Audit:** #5 — Part 1
**Markets examined:** 12

## Methodology

Active replacement markets were discovered via the Gamma API (`/events?active=true`),
ordered by most-recently started. The most recent active market per (asset, timeframe)
pair was selected. Order books were fetched from the CLOB public endpoint; last traded
price from `/last-trade-price`. Trade history (`/trades`) requires authentication and
is not publicly accessible, so first-trade timing is inferred from `last-trade-price`.

## Per-Market Forensics

### BTC

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x624e5357aff4cfca… | 2026-06-23T05:22:07 | 464299294941584726… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x4a04be120774fdb9… | 2026-06-23T05:00:00 | 812095268589836830… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x53eff5a9cd94f9ab… | 2026-06-23T05:22:06 | 745010447232648925… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T05:22:07.783901Z`
- Start date: `2026-06-23T05:28:51.932158Z`
- End date: `2026-06-24T05:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `3254.54` | Top-5 ask depth: `3888.65`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-23T05:00:00.730095Z`
- Start date: `2026-06-23T05:02:39.788975Z`
- End date: `2026-06-25T06:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `40` | Ask levels: `39`
- Top-5 bid depth: `2140.0` | Top-5 ask depth: `2635.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T05:22:06.879556Z`
- Start date: `2026-06-23T05:33:31.049282Z`
- End date: `2026-06-24T05:20:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `590.43` | Top-5 ask depth: `657.66`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xe18a81f3f690a041… | 2026-06-23T05:22:07 | 554430941678258514… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xf5b9930c640f1097… | 2026-06-23T05:00:04 | 817614652687442612… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xac77f4d56e0ab70a… | 2026-06-23T05:12:34 | 365004242536303777… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T05:22:07.682122Z`
- Start date: `2026-06-23T05:27:48.261452Z`
- End date: `2026-06-24T05:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `2619.4` | Top-5 ask depth: `3078.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-23T05:00:04.668761Z`
- Start date: `2026-06-23T05:03:07.978289Z`
- End date: `2026-06-25T06:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `38` | Ask levels: `37`
- Top-5 bid depth: `1335.0` | Top-5 ask depth: `2120.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T05:12:34.778834Z`
- Start date: `2026-06-23T05:32:29.53688Z`
- End date: `2026-06-24T05:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `35` | Ask levels: `35`
- Top-5 bid depth: `246.02` | Top-5 ask depth: `252.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x355a8046b672aeae… | 2026-06-23T05:22:05 | 871214893012553449… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x78590968e946bfa3… | 2026-06-23T05:00:06 | 886266357072454862… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x84e479ac950dcfdc… | 2026-06-23T05:27:06 | 291809597802758152… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T05:22:05.378585Z`
- Start date: `2026-06-23T05:32:00.058203Z`
- End date: `2026-06-24T05:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `31` | Ask levels: `30`
- Top-5 bid depth: `620.53` | Top-5 ask depth: `642.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-23T05:00:06.987318Z`
- Start date: `2026-06-23T05:13:51.244077Z`
- End date: `2026-06-25T06:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `18` | Ask levels: `17`
- Top-5 bid depth: `130.0` | Top-5 ask depth: `142.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T05:27:06.682625Z`
- Start date: `2026-06-23T05:30:56.215062Z`
- End date: `2026-06-24T05:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `196.0` | Top-5 ask depth: `206.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xfbe0ab5d7ab9c6fe… | 2026-06-23T05:07:06 | 216967113426291754… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x23020a8e9da5721f… | 2026-06-23T05:00:09 | 591793094097269085… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xe4aa07dc6f9646eb… | 2026-06-23T05:27:06 | 108586630075780649… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T05:07:06.292735Z`
- Start date: `2026-06-23T05:16:09.458803Z`
- End date: `2026-06-24T05:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `32` | Ask levels: `31`
- Top-5 bid depth: `352.57` | Top-5 ask depth: `376.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-23T05:00:09.137308Z`
- Start date: `2026-06-23T05:16:47.404305Z`
- End date: `2026-06-25T06:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `18` | Ask levels: `17`
- Top-5 bid depth: `130.0` | Top-5 ask depth: `135.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T05:27:06.685741Z`
- Start date: `2026-06-23T05:31:57.442548Z`
- End date: `2026-06-24T05:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `33` | Ask levels: `32`
- Top-5 bid depth: `203.0` | Top-5 ask depth: `206.0`
- Last trade price: `0.5` side: ``

## Questions Answered

**1. Was the market initially seeded at 0.50?**
   - Markets with bid ≈ 0.50 (±0.015): **12/12**

**2. Seed probability distribution:**
   - Mid range: [0.5050, 0.5050]
   - Mean mid: 0.5050
   - Note: Mid = (bid + ask) / 2. Ask is typically bid + 0.01 at creation.

**3. First trade timing:**
   Trade timestamps are not available via public API (requires auth). `last-trade-price`
   returns the most recent execution price and side but no timestamp.

**4. Did the first trade change the price?**
   - Markets where LTP ≠ 0.50: **0/12**

---
*Data fetched: 2026-06-23 05:38 UTC*