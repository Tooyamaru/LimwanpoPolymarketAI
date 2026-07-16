# LIMWANPO AI — DATA RULES (PERMANENT)

## Source
Derived from permanent project initialization document.

---

## Absolute Rule

Everything displayed inside the dashboard MUST come from official sources.

---

## Allowed Sources

| Area | Allowed Source |
|------|---------------|
| Market Universe | Polymarket ONLY |
| Prediction Cards | Polymarket ONLY |
| Prediction Status | Polymarket ONLY |
| Resolution | Polymarket ONLY |
| Liquidity | Polymarket ONLY |
| Volume | Polymarket ONLY |
| Market Metadata | Polymarket ONLY |
| Price Chart | Binance OR Chainlink ONLY (context, candlestick data) |

---

## Allowed Exceptions (Chart Only)

The price chart may use:
- **Binance** — BTC, ETH, SOL, XRP candlestick data
- **Chainlink** — oracle/reference price

No other Binance data may appear anywhere.

---

## Permanently Forbidden

The following must NEVER appear in the dashboard:

- Bid
- Ask
- Spread
- Orderbook
- Depth
- Funding Rate
- Open Interest
- PnL
- Margin
- Leverage
- Position Size
- Trading Signals

Never reintroduce these.

---

## Data Lineage Requirement (Phase 5)

Every displayed number must be able to answer: **"Where does it come from?"**

Allowed answers: Official Polymarket, Official Binance (chart only), Official Chainlink (chart only).

Not allowed: Placeholder, Random, Hardcoded, Estimated, Simulated.
