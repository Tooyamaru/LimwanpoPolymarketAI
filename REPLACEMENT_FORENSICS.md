# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 11:38:01 UTC
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
| 15m | 0x144bc269550d9105… | 2026-06-23T11:22:05 | 109431653521424947… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x900e78a3cc005d04… | 2026-06-23T11:00:00 | 955234962335706972… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x287ca6eab87e15a8… | 2026-06-23T11:27:36 | 919227283612954275… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T11:22:05.877797Z`
- Start date: `2026-06-23T11:27:48.445207Z`
- End date: `2026-06-24T11:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `36` | Ask levels: `35`
- Top-5 bid depth: `3254.54` | Top-5 ask depth: `3888.65`
- Last trade price: `0.5` side: ``

#### BTC/1H
- Created at: `2026-06-23T11:00:00.67351Z`
- Start date: `2026-06-23T11:02:07.138175Z`
- End date: `2026-06-25T12:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `1991.0` | Top-5 ask depth: `2602.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T11:27:36.003628Z`
- Start date: `2026-06-23T11:32:44.337212Z`
- End date: `2026-06-24T11:25:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `41`
- Top-5 bid depth: `600.24` | Top-5 ask depth: `668.23`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x1c828b54611accdc… | 2026-06-23T11:22:06 | 310819163761228838… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x65a29d70ef1f57d6… | 2026-06-23T11:00:04 | 493855477811686569… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x3e4153f677974096… | 2026-06-23T11:17:04 | 150322608766808404… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T11:22:06.585809Z`
- Start date: `2026-06-23T11:26:03.855442Z`
- End date: `2026-06-24T11:30:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `39` | Ask levels: `38`
- Top-5 bid depth: `2579.4` | Top-5 ask depth: `3038.51`
- Last trade price: `0.5` side: ``

#### ETH/1H
- Created at: `2026-06-23T11:00:04.636613Z`
- Start date: `2026-06-23T11:11:27.610919Z`
- End date: `2026-06-25T12:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `30` | Ask levels: `29`
- Top-5 bid depth: `1431.0` | Top-5 ask depth: `1872.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T11:17:04.078058Z`
- Start date: `2026-06-23T11:30:54.683218Z`
- End date: `2026-06-24T11:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `34` | Ask levels: `34`
- Top-5 bid depth: `271.02` | Top-5 ask depth: `298.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xf67dbc47f75d994d… | 2026-06-23T11:06:46 | 150890193265711605… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xa7059272fefc0707… | 2026-06-23T11:00:06 | 103776862990992761… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x129d4f1dccb78f72… | 2026-06-23T11:17:04 | 115622948394281500… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T11:06:46.974275Z`
- Start date: `2026-06-23T11:21:55.549828Z`
- End date: `2026-06-24T11:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `31` | Ask levels: `30`
- Top-5 bid depth: `597.53` | Top-5 ask depth: `612.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-23T11:00:06.178279Z`
- Start date: `2026-06-23T11:02:53.46584Z`
- End date: `2026-06-25T12:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `32` | Ask levels: `31`
- Top-5 bid depth: `175.0` | Top-5 ask depth: `200.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T11:17:04.172286Z`
- Start date: `2026-06-23T11:31:17.387179Z`
- End date: `2026-06-24T11:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `37` | Ask levels: `36`
- Top-5 bid depth: `203.0` | Top-5 ask depth: `213.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x3425345379d6e932… | 2026-06-23T11:06:47 | 240282481674079013… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xc4c01e0681d75e07… | 2026-06-23T11:00:07 | 424783251902124232… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x936a97c132cdc35b… | 2026-06-23T11:22:07 | 892486269099714409… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T11:06:47.787307Z`
- Start date: `2026-06-23T11:09:13.372944Z`
- End date: `2026-06-24T11:15:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `26` | Ask levels: `25`
- Top-5 bid depth: `299.57` | Top-5 ask depth: `314.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-23T11:00:07.742678Z`
- Start date: `2026-06-23T11:04:09.548782Z`
- End date: `2026-06-25T12:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `24` | Ask levels: `23`
- Top-5 bid depth: `182.0` | Top-5 ask depth: `197.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T11:22:07.485724Z`
- Start date: `2026-06-23T11:23:49.55709Z`
- End date: `2026-06-24T11:20:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `146.0` | Top-5 ask depth: `163.0`
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
*Data fetched: 2026-06-23 11:38 UTC*