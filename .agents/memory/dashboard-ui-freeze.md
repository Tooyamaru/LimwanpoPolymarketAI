---
name: Dashboard UI freeze rules
description: Rules about when the dashboard UI is considered final and what can/cannot be changed
---

# Dashboard UI — Final v1.0 (LOCKED)

## Rule
Dashboard is UI Final v1.0. Do NOT make structural layout changes. Development focus must shift to AI accuracy, signal quality, paper trading performance, and live Polymarket readiness.

## Only acceptable future UI changes
- Objective rendering bugs (broken display that was working before)
- Runtime errors or API shape changes that break display
- Security issues
- Explicit user request

## Final layout (locked)
- Row 1: 20% 55% 25% → Portfolio | Live Probability Chart | AI Activity
- Row 2: flex:1 → Market Universe (12 markets, .asset-card + .tf-list)
- Row 3: 35% 65% → System Health | Execution Pipeline
- Footer: completely frozen (DO NOT TOUCH)

## Final card structure (locked)
- Each asset column: .asset-col → .asset-card → .asset-hdr + .tf-list
- Asset subtitle (TWO LINES): "Open Position : X<br>Capital Used : $XX"
- Each timeframe inside .tf-list: .tf-card (NOT .mcard/.mcard-wrap)
- .tf-card border: rgba(0,229,255,.2) cyan, border-radius:4px, margin-bottom:6px

## Key field formats (locked)
- Position direction: "BUY YES" / "BUY NO" / "NO POSITION" (never "NONE")
- AI Score: label "AI Score", value "34/100" (never "34%" or "Eng.Score")
- Portfolio Total Capital: $400.00 (toFixed(2))
- Status colors: TRADING=NG green, MONITORING=NY yellow, WAITING=NB blue
- Status badge: inline background/border/border-radius on mc-status div

## Price to Beat logic (locked)
- parseStrike(m) extracts dollar threshold from market question via regex $XX,XXX
- Current Price = ALWAYS live Binance price from cPrices[m.asset] — NEVER the YES probability
- livePriceStr derived once, used as curPriceVal in ALL 3 branches
- Race condition fix: refresh() calls renderMarkets() AFTER Promise.all resolves (prices guaranteed)
- Difference = live - strike, green/red; shows "—" when no strike parseable
- Fallback when has position but no strike: shows entry probability % as PTB, live price as current

## System Health (locked)
- Full engine names: Signal Engine, Opportunity Engine, Strategy Engine, Risk Engine, Execution Engine, Exit Engine, Universe Sync, Price Refresh, Position Tracking, Analytics Engine
- ENGINE_ORDER includes analytics_engine as 10th entry
- .hlth-name color: #8abcda (bright)
- Values: 100% / 40% / 0% only — never OK, GOOD, PERFECT
- No debug fields: DB / REDIS / UPTIME / VERSION / MARKETS removed

## Execution Pipeline (locked)
- Icon circles: 30px×30px
- Node names: 9px font-weight:600
- Connector fline background: col+28 hex opacity
- Active node r1 glow: 0 0 18px col+44

**Why:** User declared UI Final v1.0 across multiple polish passes in Indonesian and English. All Polymarket-specific field naming, formats, and race condition fixes are now locked.
