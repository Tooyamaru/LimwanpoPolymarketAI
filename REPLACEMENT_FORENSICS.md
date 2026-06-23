# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 12:53:35 UTC
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
| 15m | 0xe7dfaee3bc9f7f0f… | 2026-06-23T12:37:37 | 164629851575557653… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd259ae2c1747f348… | 2026-06-23T12:47:03 | 114430543276596098… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T12:37:37.080827Z`
- Start date: `2026-06-23T12:38:39.303667Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `3204.54` | Top-5 ask depth: `3848.65`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T12:47:03.185953Z`
- Start date: `2026-06-23T12:48:41.913519Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `671.97` | Top-5 ask depth: `732.99`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x1aee5b05411489fc… | 2026-06-23T12:37:35 | 932486355034129971… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x38a19cc697428c22… | 2026-06-23T12:47:03 | 952758160301326084… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T12:37:35.277252Z`
- Start date: `2026-06-23T12:39:02.534865Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `2199.4` | Top-5 ask depth: `3058.51`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T12:47:03.178463Z`
- Start date: `2026-06-23T12:48:15.655258Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `41` | Ask levels: `40`
- Top-5 bid depth: `288.02` | Top-5 ask depth: `311.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x9c647d2c6a54f081… | 2026-06-23T12:37:36 | 106575699672233067… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x47e9b25c9b3ec27c… | 2026-06-23T12:47:03 | 338687492938574588… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T12:37:36.869367Z`
- Start date: `2026-06-23T12:38:53.423933Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `617.53` | Top-5 ask depth: `642.53`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T12:47:03.176832Z`
- Start date: `2026-06-23T12:48:51.1412Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `203.0` | Top-5 ask depth: `223.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x41b4cfc02f26ef88… | 2026-06-23T12:37:37 | 754626093980674816… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xef4279d0f871aa85… | 2026-06-23T12:47:05 | 924726490944589249… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T12:37:37.41362Z`
- Start date: `2026-06-23T12:38:58.601758Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `49` | Ask levels: `48`
- Top-5 bid depth: `351.57` | Top-5 ask depth: `359.57`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T12:47:05.178319Z`
- Start date: `2026-06-23T12:48:48.068469Z`
- End date: `2026-06-24T12:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `45` | Ask levels: `44`
- Top-5 bid depth: `206.0` | Top-5 ask depth: `223.0`
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
*Data fetched: 2026-06-23 12:53 UTC*