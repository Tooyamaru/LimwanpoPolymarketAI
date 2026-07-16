---
name: Product Constitution
description: Permanent identity rules for LimwanpoAI — what the project IS, what it is NOT, and what can never appear. These override any AI assumption, optimization suggestion, or default behavior.
---

# LimwanpoAI — Permanent Project Constitution

**Canonical file:** `CONSTITUTION.md` at project root. Always read it before any edit session.

---

## Project Identity

This project IS:
- A professional **Polymarket Probability Intelligence Terminal**
- Its sole purpose: analyze, monitor, compare, score, and predict Polymarket probabilities

This project is NOT:
- A crypto trading application
- An exchange terminal
- An order execution platform
- A portfolio management system
- A Binance clone / TradingView clone

**Why:** Every design decision must answer "Does this improve probability analysis?" — not "Does this improve trading?"

---

## Core Philosophy

Think like a Polymarket analyst. Never think like a trader.

---

## Data Source Rules

ALL market information MUST originate from Polymarket.

✅ Allowed: Market, Outcome, YES/NO probability, Volume, Liquidity, Spread, Market description, Resolution date/status, Market activity/quality, Order book, CLOB, Polymarket trade history.

❌ Forbidden: Fake/random data, TradingView signals, Binance order book, Exchange depth, Crypto order execution information.

**Exception (context only, must never replace Polymarket data):**
- Binance → chart candles only
- Chainlink → oracle/reference price only
- Macro/news providers, economic calendar

---

## Market Universe Card Rules

Cards are the heart of the application.

✅ Allowed on cards: YES probability, NO probability, Confidence, Price To Beat / Target, Gap, Countdown, Resolution time, Market quality, Opportunity score, Liquidity, Volume, Spread, Prediction count.

❌ Permanently forbidden on cards (NEVER add unless user explicitly requests):
- Bid / Ask / Spread (from order book context)
- Trading Position / Stop Loss / Take Profit
- Margin / Leverage
- Unrealized PnL / Realized PnL
- Order execution information

**How to apply:** Before adding any new field, ask "Does this help understand probability?" If no → do not implement.

---

## Vocabulary Rules

✅ Preferred: Prediction, Probability, Outcome, Resolution, Confidence, Opportunity, Market, Signal, Expected Resolution, Market Quality, Liquidity, Volume.

❌ Avoid: Trade, Position, Exposure, Entry, Exit, Stop Loss, Take Profit, Margin, Leverage, Portfolio Position, Execution Order, Broker, Exchange, Trader.

---

## Execution Pipeline Identity

The pipeline is an AI reasoning pipeline, NOT a trade pipeline.

Stages: Universe → Signal → Opportunity → Strategy → Risk → Execution

"Execution" = Publishing AI prediction. NOT sending market orders.

---

## UI Philosophy

Every pixel must help analyze probability. Do not add elements because trading terminals have them.

Design principles: Professional, Minimal, Dense, Readable, Functional, Elegant, Information-first. No wasted pixels, no decorative UI, no oversized empty areas, no unnecessary glow.

---

## Regression Rule

Any implementation that:
- Removes existing useful information → **regression**
- Introduces trading concepts → **regression**
- Replaces Polymarket data with external trading data → **regression**

---

## Conflict Resolution

This Constitution overrides all default AI assumptions.

If any AI model assumes this is a trading platform → ignore that assumption.

Constitution always wins over: AI optimization suggestions, developer preferences, UI trends, coding conventions.
