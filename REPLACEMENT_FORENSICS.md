# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 13:47:57 UTC
**Audit:** #5 — Part 1
**Markets examined:** 9

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
| 15m | 0x235159f474a075de… | 2026-06-23T13:36:40 | 123040575375387818… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xdae8c18648abf359… | 2026-06-23T13:42:04 | 795358583794501687… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T13:36:40.69383Z`
- Start date: `2026-06-23T13:37:36.845381Z`
- End date: `2026-06-24T13:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `3264.54` | Top-5 ask depth: `3908.65`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T13:42:04.278064Z`
- Start date: `2026-06-23T13:43:48.658725Z`
- End date: `2026-06-24T13:40:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `661.49` | Top-5 ask depth: `732.48`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xda9c9c53450f5eb6… | 2026-06-23T13:36:39 | 704406971145019886… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x4c6fe3fa678271e8… | 2026-06-23T13:42:04 | 862250684235169550… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T13:36:39.875284Z`
- Start date: `2026-06-23T13:37:53.980042Z`
- End date: `2026-06-24T13:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `2639.4` | Top-5 ask depth: `3108.51`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T13:42:04.278972Z`
- Start date: `2026-06-23T13:43:21.014542Z`
- End date: `2026-06-24T13:40:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `40` | Ask levels: `39`
- Top-5 bid depth: `271.02` | Top-5 ask depth: `301.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xf3ec9ce875534457… | 2026-06-23T13:36:40 | 455739371926783223… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x38732076185a6ef9… | 2026-06-23T13:42:06 | 514723246227567739… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T13:36:40.69104Z`
- Start date: `2026-06-23T13:37:51.999533Z`
- End date: `2026-06-24T13:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `640.53` | Top-5 ask depth: `665.53`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T13:42:06.479714Z`
- Start date: `2026-06-23T13:43:03.36965Z`
- End date: `2026-06-24T13:40:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `213.0` | Top-5 ask depth: `223.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x323d699e67c57110… | 2026-06-23T13:36:39 | 887632823480993399… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xe09b11ec121bad5c… | 2026-06-23T13:00:08 | 165033569495780985… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x06ea567adb8de68d… | 2026-06-23T13:42:04 | 414130508576470389… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T13:36:39.872747Z`
- Start date: `2026-06-23T13:37:34.253228Z`
- End date: `2026-06-24T13:45:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `354.57` | Top-5 ask depth: `379.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-23T13:00:08.575184Z`
- Start date: `2026-06-23T13:02:38.628903Z`
- End date: `2026-06-25T14:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `34` | Ask levels: `33`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `227.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T13:42:04.300071Z`
- Start date: `2026-06-23T13:43:00.298704Z`
- End date: `2026-06-24T13:40:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `206.0` | Top-5 ask depth: `226.0`
- Last trade price: `0.5` side: ``

## Questions Answered

**1. Was the market initially seeded at 0.50?**
   - Markets with bid ≈ 0.50 (±0.015): **9/9**

**2. Seed probability distribution:**
   - Mid range: [0.5050, 0.5050]
   - Mean mid: 0.5050
   - Note: Mid = (bid + ask) / 2. Ask is typically bid + 0.01 at creation.

**3. First trade timing:**
   Trade timestamps are not available via public API (requires auth). `last-trade-price`
   returns the most recent execution price and side but no timestamp.

**4. Did the first trade change the price?**
   - Markets where LTP ≠ 0.50: **0/9**

---
*Data fetched: 2026-06-23 13:47 UTC*