# REPLACEMENT_FORENSICS.md

**Generated:** 2026-06-23 13:11:00 UTC
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
| 15m | 0x0436240207fbf0f3… | 2026-06-23T12:52:35 | 562948251085267822… | 0.5 | 0.51 | 0.505 | 0.01 | 0.51 | Yes |
| 1H | 0x5b58ab6adb16cc1c… | 2026-06-23T13:00:00 | 128464949280046478… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x95cec064c0d43aa2… | 2026-06-23T13:02:06 | 593562809968269888… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### BTC/15m
- Created at: `2026-06-23T12:52:35.465565Z`
- Start date: `2026-06-23T12:53:30.338724Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `47` | Ask levels: `46`
- Top-5 bid depth: `3214.54` | Top-5 ask depth: `3848.85`
- Last trade price: `0.51` side: `BUY`

#### BTC/1H
- Created at: `2026-06-23T13:00:00.69365Z`
- Start date: `2026-06-23T13:02:00.933958Z`
- End date: `2026-06-25T14:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `38` | Ask levels: `37`
- Top-5 bid depth: `2971.0` | Top-5 ask depth: `3082.0`
- Last trade price: `0.5` side: ``

#### BTC/5m
- Created at: `2026-06-23T13:02:06.079328Z`
- Start date: `2026-06-23T13:03:13.619396Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `49` | Ask levels: `48`
- Top-5 bid depth: `523.94` | Top-5 ask depth: `607.5`
- Last trade price: `0.5` side: ``

### ETH

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x58320c5ce9eda579… | 2026-06-23T12:52:36 | 542680842020155535… | 0.5 | 0.51 | 0.505 | 0.01 | 0.51 | Yes |
| 1H | 0xdc295b2c08fc5833… | 2026-06-23T13:00:04 | 377553496420005306… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0x6d0a3677a57b1224… | 2026-06-23T13:02:06 | 904126288414903900… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### ETH/15m
- Created at: `2026-06-23T12:52:36.172595Z`
- Start date: `2026-06-23T12:53:51.439818Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `50` | Ask levels: `49`
- Top-5 bid depth: `2639.4` | Top-5 ask depth: `2715.71`
- Last trade price: `0.51` side: `BUY`

#### ETH/1H
- Created at: `2026-06-23T13:00:04.962349Z`
- Start date: `2026-06-23T13:02:03.742704Z`
- End date: `2026-06-25T14:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `42` | Ask levels: `42`
- Top-5 bid depth: `1831.0` | Top-5 ask depth: `2282.0`
- Last trade price: `0.5` side: ``

#### ETH/5m
- Created at: `2026-06-23T13:02:06.087944Z`
- Start date: `2026-06-23T13:03:57.31431Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `43` | Ask levels: `42`
- Top-5 bid depth: `246.02` | Top-5 ask depth: `289.02`
- Last trade price: `0.5` side: ``

### SOL

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0xaa4b82177392ea1e… | 2026-06-23T12:52:35 | 275580449494901473… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0x8009f642dc485c98… | 2026-06-23T13:00:06 | 145552008818156525… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xd9e2d29200daacd6… | 2026-06-23T13:02:06 | 176680732603720186… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### SOL/15m
- Created at: `2026-06-23T12:52:35.492491Z`
- Start date: `2026-06-23T12:53:52.225026Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `640.53` | Top-5 ask depth: `655.53`
- Last trade price: `0.5` side: ``

#### SOL/1H
- Created at: `2026-06-23T13:00:06.884519Z`
- Start date: `2026-06-23T13:02:05.091211Z`
- End date: `2026-06-25T14:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
- Top-5 bid depth: `185.0` | Top-5 ask depth: `217.0`
- Last trade price: `0.5` side: ``

#### SOL/5m
- Created at: `2026-06-23T13:02:06.98228Z`
- Start date: `2026-06-23T13:03:30.877019Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `44` | Ask levels: `43`
- Top-5 bid depth: `146.0` | Top-5 ask depth: `166.0`
- Last trade price: `0.5` side: ``

### XRP

| Timeframe | Condition ID (prefix) | Created At | YES Token (prefix) | Best Bid | Best Ask | Mid | Spread | LTP | Seeded at 0.50? |
|-----------|----------------------|------------|-------------------|----------|----------|-----|--------|-----|-----------------|
| 15m | 0x7bf7d541bc9be925… | 2026-06-23T12:52:36 | 317371926061260238… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 1H | 0xe09b11ec121bad5c… | 2026-06-23T13:00:08 | 165033569495780985… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |
| 5m | 0xe6c5623318c29480… | 2026-06-23T13:02:06 | 313127604818999620… | 0.5 | 0.51 | 0.505 | 0.01 | 0.5 | Yes |

**Order book top-5 depth:**

#### XRP/15m
- Created at: `2026-06-23T12:52:36.50036Z`
- Start date: `2026-06-23T12:53:33.378049Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `34` | Ask levels: `33`
- Top-5 bid depth: `334.57` | Top-5 ask depth: `349.57`
- Last trade price: `0.5` side: ``

#### XRP/1H
- Created at: `2026-06-23T13:00:08.575184Z`
- Start date: `2026-06-23T13:02:38.628903Z`
- End date: `2026-06-25T14:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `33` | Ask levels: `31`
- Top-5 bid depth: `202.0` | Top-5 ask depth: `227.0`
- Last trade price: `0.5` side: ``

#### XRP/5m
- Created at: `2026-06-23T13:02:06.098966Z`
- Start date: `2026-06-23T13:03:16.694025Z`
- End date: `2026-06-24T13:00:00Z`
- Best bid: `0.5` | Best ask: `0.51` | Mid: `0.505`
- Spread: `0.01` | Bid levels: `46` | Ask levels: `45`
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
   - Markets where LTP ≠ 0.50: **2/12**
     - ETH/15m: LTP=0.51
     - BTC/15m: LTP=0.51

---
*Data fetched: 2026-06-23 13:11 UTC*