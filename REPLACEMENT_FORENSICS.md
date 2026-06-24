# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-24 05:01:43 UTC
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
| 15m | 0x93097d61219f33aa… | 2026-06-24T04:52:01 | 533536875648859250… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x5420c32390049807… | 2026-06-24T04:52:03 | 164221492034292651… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-24T04:52:01.531563Z`
- Start date: `2026-06-24T04:52:53.70405Z`
- End date: `2026-06-25T05:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `3216.47` | Top-5 ask depth: `3850.58`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-24T04:52:03.643966Z`
- Start date: `2026-06-24T04:52:56.737888Z`
- End date: `2026-06-25T04:50:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `575.39` | Top-5 ask depth: `658.71`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xc918cc1d9ee785ce… | 2026-06-24T04:52:01 | 104419919598427687… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xfd16157c6427d258… | 2026-06-24T04:52:01 | 110946732405772893… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-24T04:52:01.593606Z`
- Start date: `2026-06-24T04:53:16.968867Z`
- End date: `2026-06-25T05:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `2626.4` | Top-5 ask depth: `3095.51`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-24T04:52:01.510358Z`
- Start date: `2026-06-24T04:53:23.039896Z`
- End date: `2026-06-25T04:50:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `256.02` | Top-5 ask depth: `299.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x307bd9229d0786ee… | 2026-06-24T04:52:01 | 101379970471927336… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xfc9b4a62204d3450… | 2026-06-24T04:52:01 | 109645127457622066… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-24T04:52:01.506205Z`
- Start date: `2026-06-24T04:52:59.042126Z`
- End date: `2026-06-25T05:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `40` | Ask levels: `39`
- Top-5 bid depth: `617.53` | Top-5 ask depth: `642.53`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-24T04:52:01.964777Z`
- Start date: `2026-06-24T04:53:11.895304Z`
- End date: `2026-06-25T04:50:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `153.0` | Top-5 ask depth: `173.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x24094f810d2448d9… | 2026-06-24T04:52:03 | 271088561429712670… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xa5592cb0ef998556… | 2026-06-24T04:52:01 | 598855310035343716… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-24T04:52:03.555265Z`
- Start date: `2026-06-24T04:52:58.768484Z`
- End date: `2026-06-25T05:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `38` | Ask levels: `37`
- Top-5 bid depth: `351.57` | Top-5 ask depth: `366.57`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-24T04:52:01.607704Z`
- Start date: `2026-06-24T04:53:07.766587Z`
- End date: `2026-06-25T04:50:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `161.0` | Top-5 ask depth: `173.0`
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
*Data fetched: 2026-06-24 05:01 UTC*