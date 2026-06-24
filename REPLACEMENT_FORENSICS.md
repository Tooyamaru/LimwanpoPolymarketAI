# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-24 06:34:56 UTC
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
| 15m | 0x67f39b2ba6e37666… | 2026-06-24T06:22:36 | 200716362627920535… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xc1b370d5a9e5b733… | 2026-06-24T06:00:00 | 772791179817526885… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x5f8d6d8b2828222c… | 2026-06-24T06:27:02 | 890438233790378482… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-24T06:22:36.437583Z`
- Start date: `2026-06-24T06:23:51.232643Z`
- End date: `2026-06-25T06:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `45` | Ask levels: `44`
- Top-5 bid depth: `3301.54` | Top-5 ask depth: `3945.65`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-24T06:00:00.677047Z`
- Start date: `2026-06-24T06:00:14Z`
- End date: `2026-06-26T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `44` | Ask levels: `43`
- Top-5 bid depth: `2398.0` | Top-5 ask depth: `3009.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-24T06:27:02.952343Z`
- Start date: `2026-06-24T06:28:01.3371Z`
- End date: `2026-06-25T06:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `552.39` | Top-5 ask depth: `623.21`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x50f2506da6a89947… | 2026-06-24T06:22:37 | 107384179933529540… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xf21d63abbcf093f5… | 2026-06-24T06:00:02 | 332169634569907902… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x7d4e2c2b89781735… | 2026-06-24T06:27:03 | 397818990158335733… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-24T06:22:37.949226Z`
- Start date: `2026-06-24T06:23:36.152525Z`
- End date: `2026-06-25T06:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `2656.4` | Top-5 ask depth: `3125.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-24T06:00:02.713373Z`
- Start date: `2026-06-24T06:00:14Z`
- End date: `2026-06-26T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `1858.0` | Top-5 ask depth: `2309.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-24T06:27:03.035471Z`
- Start date: `2026-06-24T06:28:01.063165Z`
- End date: `2026-06-25T06:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `246.02` | Top-5 ask depth: `289.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xcca18bfefc6c76d2… | 2026-06-24T06:22:36 | 111795480530912197… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x0c060b55a2e1c031… | 2026-06-24T06:00:04 | 538346840728208912… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xdc9867cf195d277e… | 2026-06-24T06:27:02 | 906344489732348044… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-24T06:22:36.067754Z`
- Start date: `2026-06-24T06:23:48.225598Z`
- End date: `2026-06-25T06:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `44` | Ask levels: `43`
- Top-5 bid depth: `647.53` | Top-5 ask depth: `662.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-24T06:00:04.264253Z`
- Start date: `2026-06-24T06:00:16Z`
- End date: `2026-06-26T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `48` | Ask levels: `47`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `227.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-24T06:27:02.935133Z`
- Start date: `2026-06-24T06:28:10.215436Z`
- End date: `2026-06-25T06:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `153.0` | Top-5 ask depth: `173.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xcb33e9e1414e4ded… | 2026-06-24T06:22:36 | 177066063302180352… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x39c3bc70e829c656… | 2026-06-24T06:00:05 | 772290952087913368… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd1c1894ee8adb296… | 2026-06-24T06:27:03 | 752313691108670048… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-24T06:22:36.472627Z`
- Start date: `2026-06-24T06:23:40.277341Z`
- End date: `2026-06-25T06:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `371.57` | Top-5 ask depth: `386.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-24T06:00:05.834754Z`
- Start date: `2026-06-24T06:00:19Z`
- End date: `2026-06-26T07:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `15` | Ask levels: `14`
- Top-5 bid depth: `87.0` | Top-5 ask depth: `102.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-24T06:27:03.546885Z`
- Start date: `2026-06-24T06:27:59.033306Z`
- End date: `2026-06-25T06:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `163.0` | Top-5 ask depth: `183.0`
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
*Data fetched: 2026-06-24 06:34 UTC*