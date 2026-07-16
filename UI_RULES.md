# LIMWANPO AI — UI RULES (PERMANENT)

## Source
Derived from permanent project initialization document.

---

## Prediction Card — Required Fields (Always Visible)

Every prediction card MUST always contain:

- Movement (UP / DOWN direction)
- UP Probability
- DOWN Probability
- Target
- Gap
- Confidence
- Countdown
- Status

When a prediction exists, these additional fields must also remain visible:

- Open At
- Coverage
- Entries

---

## Immutability Rules

- Never remove any of the above fields.
- Never compress them away.
- Never hide them.
- Never replace them.
- Never invent new rows.

---

## Permanently Forbidden UI Elements

- Bid / Ask
- Spread (from order book context)
- Orderbook widget
- Trading widgets of any kind
- Stop Loss / Take Profit labels
- Margin / Leverage indicators
- PnL / Unrealized PnL display

---

## Layout Rules

- Never redesign the dashboard.
- Never move panels unless explicitly requested.
- Never reorder the layout.
- Never add new cards without explicit instruction.
- Never remove existing information.
- Never compress information by deleting content.
- If additional space is needed: optimize spacing, NOT information.

---

## Regression Checklist (run before every UI change)

Verify all of the following remain visible after any change:

- [ ] Target
- [ ] Gap
- [ ] Confidence
- [ ] Countdown
- [ ] Status
- [ ] Coverage
- [ ] Entries
- [ ] Open At
- [ ] Prediction State

If any item disappears: **ROLL BACK immediately.**

---

## Design Principles

Professional · Minimal · Dense · Readable · Functional · Elegant · Information-first

No wasted pixels · No decorative UI · No oversized empty areas · No unnecessary glow
