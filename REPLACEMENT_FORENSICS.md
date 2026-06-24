# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-24 03:19:25 UTC
**Audit:** #5 — Part 1
**Markets examined:** 8

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
| 15m | 0x78ac235e18bcb4c2… | 2026-06-24T03:06:39 | 531355549932160676… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xff1efa798a8f2584… | 2026-06-24T03:11:31 | 826466334109132782… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-24T03:06:39.737758Z`
- Start date: `2026-06-24T03:07:58.199655Z`
- End date: `2026-06-25T03:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `3209.47` | Top-5 ask depth: `3853.58`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-24T03:11:31.133138Z`
- Start date: `2026-06-24T03:12:26.23753Z`
- End date: `2026-06-25T03:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `595.32` | Top-5 ask depth: `682.5`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xda822ffdd5d2f474… | 2026-06-24T03:06:39 | 366917439994924095… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xc9f72f4854bbf240… | 2026-06-24T03:11:31 | 606097570979639741… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-24T03:06:39.451232Z`
- Start date: `2026-06-24T03:07:39.076152Z`
- End date: `2026-06-25T03:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `2599.4` | Top-5 ask depth: `3068.51`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-24T03:11:31.40644Z`
- Start date: `2026-06-24T03:12:31.115603Z`
- End date: `2026-06-25T03:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `239.02` | Top-5 ask depth: `282.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x9eaa3b45ca16e833… | 2026-06-24T03:06:39 | 873377059426580068… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd540db458599ef41… | 2026-06-24T03:11:31 | 131906978234612048… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-24T03:06:39.192224Z`
- Start date: `2026-06-24T03:07:41.139933Z`
- End date: `2026-06-25T03:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `44` | Ask levels: `43`
- Top-5 bid depth: `597.53` | Top-5 ask depth: `612.53`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-24T03:11:31.406397Z`
- Start date: `2026-06-24T03:12:32.137637Z`
- End date: `2026-06-25T03:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `44` | Ask levels: `43`
- Top-5 bid depth: `146.0` | Top-5 ask depth: `156.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xb25538e6ced1b62f… | 2026-06-24T03:06:39 | 110491290395642705… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x2cb96523fdd3765c… | 2026-06-24T03:11:30 | 976692476877804087… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-24T03:06:39.432782Z`
- Start date: `2026-06-24T03:07:48.005443Z`
- End date: `2026-06-25T03:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `351.57` | Top-5 ask depth: `369.57`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-24T03:11:30.950982Z`
- Start date: `2026-06-24T03:12:28.298695Z`
- End date: `2026-06-25T03:10:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `134.0` | Top-5 ask depth: `156.0`
- Last trade price: `0.5` side: ``

## Questions Answered

**1. Was the market initially seeded at 0.50?**
   - Markets with bid ≈ 0.50 (±0.015): **8/8**

**2. Seed probability distribution:**
   - Mid range: [0.5050, 0.5050]
   - Mean mid: 0.5050
   - Note: Mid = (bid + ask) / 2. Ask is typically bid + 0.01 at creation.

**3. First trade timing:**
   Trade timestamps are not available via public API (requires auth). `last-trade-price`
   returns the most recent execution price and side but no timestamp.

**4. Did the first trade change the price?**
   - Markets where LTP ≠ 0.50: **0/8**

---
*Data fetched: 2026-06-24 03:19 UTC*