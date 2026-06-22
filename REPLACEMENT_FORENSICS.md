# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-22 06:22:16 UTC
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
| 15m | 0xa15afd0ac7868ac9… | 2026-06-22T06:06:46 | 674770968285004165… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x003338a1d838e2ca… | 2026-06-22T06:00:00 | 911885354069996694… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x21647d51de3e9528… | 2026-06-22T06:13:40 | 612085126304423348… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-22T06:06:46.679573Z`
- Start date: `2026-06-22T06:07:47.550779Z`
- End date: `2026-06-23T06:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `3244.47` | Top-5 ask depth: `3876.58`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-22T06:00:00.651919Z`
- Start date: `2026-06-22T06:02:10.871077Z`
- End date: `2026-06-24T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `2390.0` | Top-5 ask depth: `2980.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-22T06:13:40.716755Z`
- Start date: `2026-06-22T06:14:32.295067Z`
- End date: `2026-06-23T06:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `558.51` | Top-5 ask depth: `602.37`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x604a0ae2897a8d9f… | 2026-06-22T06:06:48 | 101004094683910595… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x9affefc36586cd99… | 2026-06-22T06:00:02 | 260350336975410463… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd252dd325f6f19d5… | 2026-06-22T06:13:42 | 321241531779592609… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-22T06:06:48.086002Z`
- Start date: `2026-06-22T06:07:55.498243Z`
- End date: `2026-06-23T06:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `2607.4` | Top-5 ask depth: `3069.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-22T06:00:02.992274Z`
- Start date: `2026-06-22T06:02:06.738142Z`
- End date: `2026-06-24T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `1825.0` | Top-5 ask depth: `1875.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-22T06:13:42.677664Z`
- Start date: `2026-06-22T06:14:39.24642Z`
- End date: `2026-06-23T06:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `247.02` | Top-5 ask depth: `283.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x0df5610235843e09… | 2026-06-22T06:06:48 | 282756244799898810… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xeca9ded09f515b8a… | 2026-06-22T06:00:04 | 781451999591281640… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd7fdcd7d1e27315a… | 2026-06-22T06:13:42 | 177616509661227337… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-22T06:06:48.082547Z`
- Start date: `2026-06-22T06:07:49.817361Z`
- End date: `2026-06-23T06:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `607.53` | Top-5 ask depth: `627.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-22T06:00:04.711273Z`
- Start date: `2026-06-22T06:02:04.772881Z`
- End date: `2026-06-24T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `222.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-22T06:13:42.883653Z`
- Start date: `2026-06-22T06:14:38.243071Z`
- End date: `2026-06-23T06:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `163.0` | Top-5 ask depth: `168.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xe163b9264c5072dd… | 2026-06-22T06:06:47 | 940675006225201888… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x3c7503a8fd09728f… | 2026-06-22T06:00:06 | 331751627603631772… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x48eef81a63d1036b… | 2026-06-22T06:13:40 | 804191306189645585… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-22T06:06:47.486108Z`
- Start date: `2026-06-22T06:07:42.714572Z`
- End date: `2026-06-23T06:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `361.57` | Top-5 ask depth: `381.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-22T06:00:06.708908Z`
- Start date: `2026-06-22T06:02:09.802239Z`
- End date: `2026-06-24T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `41`
- Top-5 bid depth: `195.0` | Top-5 ask depth: `215.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-22T06:13:40.718502Z`
- Start date: `2026-06-22T06:14:33.324913Z`
- End date: `2026-06-23T06:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `146.0` | Top-5 ask depth: `161.0`
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
*Data fetched: 2026-06-22 06:22 UTC*