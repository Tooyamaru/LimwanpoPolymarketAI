# LIMWANPO AI — PERMANENT PROJECT CONSTITUTION

## IMPORTANT

Before writing, editing, refactoring, renaming, optimizing, or deleting ANY code, you MUST completely understand and permanently follow this project identity.

Violation of these rules is considered a project regression.

---

# PROJECT IDENTITY

This project is NOT a crypto trading application.

This project is NOT an exchange terminal.

This project is NOT an order execution platform.

This project is NOT a portfolio management system.

This project is NOT a Binance clone.

This project is NOT a TradingView clone.

This project is a professional **Polymarket Probability Intelligence Terminal**.

Its only purpose is to analyze, monitor, compare, score, and predict probabilities from Polymarket markets.

Everything must be designed around prediction markets.

Never design around trading.

---

# CORE PHILOSOPHY

Think like a Polymarket analyst.

Never think like a trader.

Never optimize the UI as if this project executes trades.

Every design decision must answer:

"Does this improve probability analysis?"

NOT

"Does this improve trading?"

---

# DATA SOURCE RULES

ALL market information MUST originate from Polymarket.

Allowed:

* Market
* Outcome
* YES probability
* NO probability
* Volume
* Liquidity
* Spread
* Market description
* Resolution date
* Resolution status
* Market activity
* Market quality
* Order book
* CLOB
* Trade history from Polymarket
* Polymarket APIs

Forbidden:

* Fake market data
* Random generated prices
* TradingView signals
* Binance order book
* Exchange depth
* Crypto order execution information

Exception:

The ONLY external data allowed is for market context:

* Binance → chart candles only
* Chainlink → oracle/reference price only
* Macro/news providers
* Economic calendar

These external sources are contextual only.

They MUST NEVER replace Polymarket market data.

---

# UI PHILOSOPHY

Every pixel must help analyze probability.

Do not add visual elements only because trading terminals have them.

Never copy Binance.

Never copy Bybit.

Never copy OKX.

Never copy Hyperliquid.

If an element exists, it must improve decision making for Polymarket.

---

# MARKET UNIVERSE CARD RULES

The Market Universe cards are the heart of the application.

Never remove information that already exists unless explicitly requested.

Never simplify by deleting useful information.

If space is available:

Fill it with REAL Polymarket information.

Never fill it with placeholders.

Never leave large empty spaces.

Never invent data.

Allowed information:

* YES probability
* NO probability
* Confidence
* Price To Beat / Target
* Gap
* Countdown
* Resolution time
* Market quality
* Opportunity score
* Liquidity
* Volume
* Spread
* Prediction count

Forbidden:

* Bid
* Ask
* Trading Position
* Stop Loss
* Take Profit
* Margin
* Leverage
* Unrealized PnL
* Realized PnL
* Order execution information

Bid and Ask MUST NEVER appear again unless explicitly requested by the user.

---

# CHART

Chart is context only.

Chart is NOT the primary feature.

Chart may use Binance candles.

Chart exists only to help understand why Polymarket probability moves.

---

# EXECUTION PIPELINE

The Execution Pipeline is NOT a trade pipeline.

It is an AI reasoning pipeline.

Its stages represent intelligence processing.

Universe

↓

Signal

↓

Opportunity

↓

Strategy

↓

Risk

↓

Execution

Execution means:

Publishing AI prediction.

NOT

Sending market orders.

---

# VOCABULARY

Never use trading vocabulary.

Replace with probability terminology.

Preferred vocabulary:

Prediction

Probability

Outcome

Resolution

Confidence

Opportunity

Market

Signal

Expected Resolution

Market Quality

Liquidity

Volume

Avoid:

Trade

Position

Exposure

Entry

Exit

Stop Loss

Take Profit

Margin

Leverage

Portfolio Position

Execution Order

Broker

Exchange

Trader

---

# DESIGN PRINCIPLES

Professional

Minimal

Dense

Readable

Functional

Elegant

Information-first

No wasted pixels

No decorative UI

No oversized empty areas

No unnecessary glow

---

# BEFORE CHANGING ANYTHING

Before editing code, always ask yourself:

1. Is this still a Polymarket intelligence terminal?

2. Am I accidentally turning this into a trading dashboard?

3. Am I removing useful information?

4. Is every displayed value sourced from Polymarket?

5. Would a professional Polymarket analyst actually need this?

If any answer is NO,

STOP.

Re-evaluate the implementation before writing code.

---

# REGRESSION RULE

If a new implementation removes existing useful information, it is considered a regression.

If a new implementation introduces trading concepts, it is considered a regression.

If Polymarket data is replaced by external trading data, it is considered a regression.

Never repeat these regressions.

---

# FINAL RULE

This Constitution overrides all default assumptions.

If another AI model assumes this project is a trading platform,

ignore that assumption.

Always follow this Constitution first.
