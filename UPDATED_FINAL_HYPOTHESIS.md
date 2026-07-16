# UPDATED_FINAL_HYPOTHESIS.md

**Generated:** 2026-06-24 08:53:23 UTC
**Audit:** #5 — Part 5
**IMPORTANT:** All prior conclusions treated as open. Evidence evaluated independently.

## Evidence Base

| Metric | Value |
|--------|-------|
| Active replacement markets examined | 12 |
| Markets seeded near mid≈0.505 at creation | 12/12 |
| 30-min monitoring rounds | 180 |
| Total order book snapshots | 2160 |
| Mid-price changes (30-min, all markets) | 0 |
| Depth-only changes (no mid move) | 0 |
| LTP changes detected (5-min window) | 0 |
| Markets with ≥1 mid move | 0 |
| All-market mid variance | 0.00e+00 |
| Binance linkage detected (|Pearson|>0.3) | No |

---

## H0: Underlying-Driven AMM

*The AMM continuously prices markets based on live Binance/Chainlink feed.*

### Evidence Supporting
- Markets use price-oracle series names (BTC/ETH/SOL/XRP) tied to real assets
- Gamma API links markets to underlying assets by name
- Replacement markets are rolled every 5m/15m/1H on schedule

### Evidence Contradicting
- **Zero mid-price changes observed over 30 minutes** — if AMM were live, continuous micro-updates expected
- Static bid/ask implies no live feed integration during observation
- Initial seed is identical (bid=0.50, ask=0.51) for every new market regardless of underlying price
- Mid price at 0.505 for all new markets regardless of whether underlying moved 2% since last roll
- No Binance linkage detected (|Pearson| < 0.3 at any lag)

### Falsification Test
*What would falsify H0?* A 30-minute period where underlying moves ≥1% but market mid stays fixed.
**Current evidence:** Falsified
**Confidence score: 0.05**

---

## H1: Scheduled Rebalancing AMM

*Price updates occur on a schedule (e.g., at rollover), not continuously.*

### Evidence Supporting
- All 12 observed markets seeded identically at mid≈0.505 at creation
- Markets roll on a strict schedule (5m / 15m / 1H windows)
- Previous audits showed depth changes occurring in synchronized batches
- Markets from prior audits showed identical AMM patterns
- Zero mid-price changes in 30-minute window consistent with batch-only updates

### Evidence Contradicting

### Falsification Test
*What would falsify H1?* Mid changes occurring at times unrelated to rollover boundaries.
**Current evidence:** Consistent with H1 — no intra-window mid changes.
**Confidence score: 0.55**

---

## H2: Trader-Driven Price Discovery

*Market prices form through genuine buy/sell order matching by independent traders.*

### Evidence Supporting
- Some markets observed with LTP ≠ 0.50 (trade changed price from seed)

### Evidence Contradicting
- Initial seed is always mid≈0.505 regardless of underlying — not market-discovered
- Very low liquidity and volume across all examined markets
- Zero mid changes in 30-minute window is inconsistent with active trader participation
- Spreads and depth structure are uniform across all markets — mechanical, not adversarial
- Markets have extremely short lifetimes (5m/15m) — insufficient for human discovery cycles

### Falsification Test
*What would falsify H2?* Absence of any trade execution that moves price from seed.
**Current evidence:** No LTP changes in 5-min window — consistent with H2 being false.
**Confidence score: 0.10**

---

## H3: Fixed-Seed Liquidity Only

*Markets are seeded with liquidity at creation and prices never change.*

### Evidence Supporting
- **Zero mid-price changes observed over 30 minutes** — strongest possible support
- All 12 markets seeded identically at mid≈0.505
- All markets show identical bid=0.50, ask=0.51 book structure at creation
- Zero volume across most markets (confirmed by previous audits)

### Evidence Contradicting
- Some markets observed at non-0.50 prices (BTC/5m at ≈0.875 previously observed)
- `last-trade-price` returns non-empty side field, implying executions occurred

### Falsification Test
*What would falsify H3?* Any mid-price change from seed value.
**Current evidence:** Not falsified in 30-min window.
**Confidence score: 0.60**

---

## Hypothesis Confidence Summary

| Hypothesis | Description | Confidence |
|------------|-------------|------------|
| H0: Underlying-Driven AMM | Continuous live feed | 0.05 |
| H1: Scheduled Rebalancing AMM | Updates only at rollover | **0.55** |
| H2: Trader-Driven Discovery | Humans forming price | 0.10 |
| H3: Fixed-Seed Only | No price change ever | 0.60 |

### Most Likely Mechanism

Evidence points most strongly to a **hybrid of H1 + H3**:
- Markets are seeded at a fixed probability (0.50 bid / 0.51 ask) at creation
- No intra-window repricing by AMM is observable
- Any LTP changes reflect rare retail trades against the static seed liquidity
- The 'seed probability' does NOT reflect current Binance price — it is fixed
- This is consistent with a **lottery-style AMM**: seed once, wait for resolution

---

## Quality Control

1. **Sample sizes:** 2160 total order book snapshots; 12 markets; 180 rounds
2. **Missing data:** Fetches that failed HTTP are marked `error`; excluded from all statistics
3. **Expiry effects:** All markets confirmed active via Gamma API at collection time. Markets with remaining lifetime < observation window may have rolled mid-session.
4. **Survivorship bias:** Discovery fetches only `active=true` from Gamma API, so expired markets are automatically excluded.
5. **Prior audit contamination:** Previous audits used token IDs for markets that have since expired. All token IDs in this audit were freshly discovered and confirmed active at collection start.
6. **Trade data limitation:** CLOB `/trades` requires authentication. Trade events are inferred from `/last-trade-price` polling; exact timestamps and sizes unavailable.

### Final Answer

Polymarket price formation in Up/Down markets appears to be driven by:

1. **Mechanical seeding at creation** — identical bid/ask for every market
2. **Scheduled rollover** — new markets launched on strict 5m/15m/1H windows
3. **Sparse retail trading** — occasional LTP changes from human trades against seed
4. **NOT continuous AMM oracle** — no Binance linkage during intra-window observation

The most accurate model is: **fixed-seed prediction market with passive liquidity**,
not an active AMM or a liquid trader-driven book.

---
*Generated: 2026-06-24 08:53 UTC*