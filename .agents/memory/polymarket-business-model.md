---
name: Polymarket Business Model
description: Authoritative business rules for this prediction-market system — must be applied in all future audits and design decisions.
---

## Core Identity
This is a Polymarket prediction market engine, NOT a Binance/futures/spot/options trading bot.

## External Data Sources (signal input only)
Binance, Chainlink, and other market data providers are used EXCLUSIVELY for:
- Signal generation
- Trend analysis
- Volatility analysis
- Prediction modeling

They are NOT the traded asset. The traded asset is the Polymarket prediction contract.

## Valid Decision Types (explicit, user-confirmed)
- OPEN_LONG_YES — buy YES contract
- OPEN_LONG_NO  — buy NO contract
- CLOSE_POSITION — exit an open position (profit-taking or stop-loss)

## Target Markets
- BTC (Bitcoin)
- ETH (Ethereum)
- SOL (Solana)
- BNB (Binance Coin)

Note: Current settings.py and README.md list XRP instead of BNB. This is a discrepancy vs stated business model.

## Market Outcome Structure
Binary only: YES or NO resolution.

## Position Rules
- Multiple simultaneous positions on the same market MAY be allowed depending on portfolio exposure rules.
- Exposure management is more important than raw position count.
- One-position-per-market is NOT a hard rule unless explicitly coded as such.
- DUPLICATE_POSITION rule in risk_engine.py (one OPEN per condition_id) may conflict with this intent — requires design decision.

## Exit Rules
- Positions do NOT need to remain open until market resolution.
- Profit-taking exits before event settlement are valid and expected behavior.
- Market expiry is NOT required to trigger position closure.
- `close_position()` in position_service.py is the correct mechanism for this.

## Audit Rules (mandatory for all future audits)
1. Evaluate ALL findings against prediction-market assumptions, not futures/spot/options logic.
2. Multiple entries on same market are NOT automatically duplicates — only flag if they violate explicit exposure rules in source code.
3. When business intent conflicts with generic trading assumptions, business intent takes precedence.
4. CLOSE_POSITION is a first-class decision type — its absence in strategy_engine is a gap, not a design choice.
5. Profit-taking / early exit logic must be treated as valid behavior, not errors.

**Why:** User provided explicit, formal business model clarification on 2026-06-23 after initial audit misclassified D-01 and D-07 using futures-trading logic.
