# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-24 08:18:15 UTC
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
| 15m | 0x7a56aab463809cf0… | 2026-06-24T08:07:14 | 272860788467084955… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xcdeaa49aabacd237… | 2026-06-24T08:00:00 | 265248520107067770… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x44a8508b233599d0… | 2026-06-24T08:07:05 | 101062586572705645… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-24T08:07:14.093515Z`
- Start date: `2026-06-24T08:08:33.215018Z`
- End date: `2026-06-25T08:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `3241.54` | Top-5 ask depth: `3885.65`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-24T08:00:00.696559Z`
- Start date: `2026-06-24T08:00:12Z`
- End date: `2026-06-26T09:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `2408.0` | Top-5 ask depth: `3019.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-24T08:07:05.169671Z`
- Start date: `2026-06-24T08:08:24.15589Z`
- End date: `2026-06-25T08:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `640.34` | Top-5 ask depth: `714.47`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x92678786e1957bc6… | 2026-06-24T08:07:06 | 313178304965662512… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x8979405cecff9622… | 2026-06-24T08:00:03 | 114933244725357837… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xa983763d2ff860e8… | 2026-06-24T08:07:07 | 895336045939467256… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-24T08:07:06.627552Z`
- Start date: `2026-06-24T08:08:23.126797Z`
- End date: `2026-06-25T08:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `49` | Ask levels: `48`
- Top-5 bid depth: `2606.4` | Top-5 ask depth: `3075.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-24T08:00:03.027271Z`
- Start date: `2026-06-24T08:00:14Z`
- End date: `2026-06-26T09:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `1848.0` | Top-5 ask depth: `2289.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-24T08:07:07.170822Z`
- Start date: `2026-06-24T08:08:17.00928Z`
- End date: `2026-06-25T08:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `246.02` | Top-5 ask depth: `279.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xbae750eda0737800… | 2026-06-24T08:07:06 | 808871870832642499… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x04d80611c5850583… | 2026-06-24T08:00:04 | 959583394844936875… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x8aa828f2364a7af9… | 2026-06-24T08:07:06 | 113590040215809662… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-24T08:07:06.484501Z`
- Start date: `2026-06-24T08:08:30.395007Z`
- End date: `2026-06-25T08:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `49` | Ask levels: `47`
- Top-5 bid depth: `617.53` | Top-5 ask depth: `642.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-24T08:00:04.630731Z`
- Start date: `2026-06-24T08:01:40Z`
- End date: `2026-06-26T09:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `217.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-24T08:07:06.1336Z`
- Start date: `2026-06-24T08:08:20.204832Z`
- End date: `2026-06-25T08:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `163.0` | Top-5 ask depth: `183.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x76e210604dff98e9… | 2026-06-24T08:07:07 | 385130757241963845… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x58ea0a55bcb6a5a4… | 2026-06-24T08:00:06 | 620320236244341115… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x5498b0449cd17219… | 2026-06-24T08:07:05 | 124030102007913287… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-24T08:07:07.260102Z`
- Start date: `2026-06-24T08:08:02.614398Z`
- End date: `2026-06-25T08:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `35` | Ask levels: `34`
- Top-5 bid depth: `341.57` | Top-5 ask depth: `356.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-24T08:00:06.393405Z`
- Start date: `2026-06-24T08:00:17Z`
- End date: `2026-06-26T09:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `41`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `227.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-24T08:07:05.182466Z`
- Start date: `2026-06-24T08:08:11.271561Z`
- End date: `2026-06-25T08:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `49` | Ask levels: `48`
- Top-5 bid depth: `153.0` | Top-5 ask depth: `173.0`
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
*Data fetched: 2026-06-24 08:18 UTC*