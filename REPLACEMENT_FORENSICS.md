# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 14:14:42 UTC
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
| 15m | 0x2eac8851caf1d99d… | 2026-06-23T14:07:04 | 487328715325179934… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x50bc051d8652ccdb… | 2026-06-23T14:00:00 | 842543247706794499… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x26e2ba24e38232dd… | 2026-06-23T14:07:02 | 881663106936339611… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T14:07:04.876742Z`
- Start date: `2026-06-23T14:08:19.64326Z`
- End date: `2026-06-24T14:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `3264.47` | Top-5 ask depth: `3908.58`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-23T14:00:00.757448Z`
- Start date: `2026-06-23T14:01:57.265105Z`
- End date: `2026-06-25T15:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `2971.0` | Top-5 ask depth: `3092.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T14:07:02.56396Z`
- Start date: `2026-06-23T14:08:23.500409Z`
- End date: `2026-06-24T14:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `685.61` | Top-5 ask depth: `756.63`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x37e26fd3c65b59b2… | 2026-06-23T14:07:06 | 330393105615392517… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x3db16288458ea270… | 2026-06-23T14:00:05 | 481848108920709313… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x23535dfb067ef05f… | 2026-06-23T14:07:06 | 128703812929508344… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T14:07:06.383758Z`
- Start date: `2026-06-23T14:08:15.667597Z`
- End date: `2026-06-24T14:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `41`
- Top-5 bid depth: `2629.4` | Top-5 ask depth: `3098.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-23T14:00:05.474908Z`
- Start date: `2026-06-23T14:02:00.294956Z`
- End date: `2026-06-25T15:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `34` | Ask levels: `33`
- Top-5 bid depth: `1821.0` | Top-5 ask depth: `2262.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T14:07:06.98178Z`
- Start date: `2026-06-23T14:08:21.676122Z`
- End date: `2026-06-24T14:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `41`
- Top-5 bid depth: `306.02` | Top-5 ask depth: `349.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xc87c96ae45843dd7… | 2026-06-23T14:07:06 | 740786500405700289… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xa598521bc8ea8a89… | 2026-06-23T14:00:07 | 940128599726660143… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xe10fa2ee3676d709… | 2026-06-23T14:07:02 | 994302128940291605… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T14:07:06.98169Z`
- Start date: `2026-06-23T14:08:13.274801Z`
- End date: `2026-06-24T14:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `640.53` | Top-5 ask depth: `665.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-23T14:00:07.856182Z`
- Start date: `2026-06-23T14:02:17.305889Z`
- End date: `2026-06-25T15:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `182.0` | Top-5 ask depth: `197.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T14:07:02.561545Z`
- Start date: `2026-06-23T14:07:55.822276Z`
- End date: `2026-06-24T14:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `146.0` | Top-5 ask depth: `166.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x3026fd63b9a8ada2… | 2026-06-23T14:07:02 | 624810952670435577… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x11251e7c1bdf23db… | 2026-06-23T14:00:09 | 519250344066023142… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xbd73df62de046176… | 2026-06-23T14:07:05 | 104308425973442898… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T14:07:02.578718Z`
- Start date: `2026-06-23T14:08:00.425968Z`
- End date: `2026-06-24T14:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `33` | Ask levels: `32`
- Top-5 bid depth: `371.57` | Top-5 ask depth: `386.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-23T14:00:09.427369Z`
- Start date: `2026-06-23T14:02:16.932941Z`
- End date: `2026-06-25T15:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `182.0` | Top-5 ask depth: `197.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T14:07:05.175876Z`
- Start date: `2026-06-23T14:08:15.392207Z`
- End date: `2026-06-24T14:05:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `206.0` | Top-5 ask depth: `216.0`
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
*Data fetched: 2026-06-23 14:14 UTC*