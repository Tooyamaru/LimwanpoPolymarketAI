# LIMWANPO AI — AI GUARDIAN KERNEL (PERMANENT VALIDATION LAYER)

## ARCHITECTURE (PERMANENT)

There is only one production application in this repository: `backend/`. There is only one workflow and one port.

Mockup Sandbox has been permanently retired (2026-07-08). Future AI must never recreate or re-enable a second application.

## MANDATORY

This document is permanent.

Every future coding session — by any AI (Replit AI, Claude, ChatGPT, Gemini, or any other) — MUST read and pass every gate in this document BEFORE touching any code.

Failure to pass any gate = STOP. Do not proceed.

---

## SECTION A — GUARDIAN AUTHORITY

AI_GUARDIAN is NOT a project phase.

AI_GUARDIAN is NOT documentation only.

AI_GUARDIAN is the **permanent validation kernel** of LIMWANPO AI.

Every coding session must execute AI_GUARDIAN before any code modification — without exception.

### Authority Hierarchy

```
Operating System (Permanent Project OS)
        ↓
Constitution (CONSTITUTION.md)
        ↓
Project Rules (PROJECT_RULES.md)
        ↓
Data Rules (DATA_RULES.md)
        ↓
UI Rules (UI_RULES.md)
        ↓
Phase Gate (PHASE_GATE.md)
        ↓
AI Guardian ← YOU ARE HERE (KERNEL)
        ↓
Audit (pre-code + post-code)
        ↓
Coding (only if all gates PASS)
```

AI_GUARDIAN sits above every phase. It cannot be skipped, suspended, or overridden by any phase instruction, user shortcut, or AI optimisation suggestion.

---

## SECTION B — PERMISSION SYSTEM

Before ANY coding begins, Guardian MUST execute all 7 checks and output the result.

### Required Output Format

```
GUARDIAN PERMISSION CHECK
─────────────────────────
Identity       : PASS / FAIL
Source         : PASS / FAIL
Vocabulary     : PASS / FAIL
Regression     : PASS / FAIL
Layout         : PASS / FAIL
Phase          : PASS / FAIL
Data Integrity : PASS / FAIL
─────────────────────────
PERMISSION GRANTED   ←  all PASS
      — or —
PERMISSION DENIED    ←  any FAIL
```

If **every item is PASS** → output `PERMISSION GRANTED` and proceed.

If **any item is FAIL** → output `PERMISSION DENIED`. Stop immediately. No coding. Explain the failure. Wait for user direction.

---

## SECTION C — SOURCE VALIDATOR

Guardian must verify that EVERY displayed value has EXACTLY ONE approved source.

**Allowed sources:**

| Source | Scope |
|--------|-------|
| Polymarket | Market data, probabilities, resolution, volume, liquidity |
| Binance Chart | Candlestick data and reference price (chart context only) |
| Chainlink | Oracle/reference price (chart context only) |
| Internal Engine | Confidence, Gap, AI Activity, Health, Pipeline, Budget |

**Automatic FAIL conditions:**

- Source is unknown
- Source is a placeholder / hardcoded value
- Source is `Math.random()` or any generated value
- Source is estimated or simulated
- Source is duplicated (same value from two conflicting origins)
- Source is any external service not listed above

If source validation fails → **FAIL. Do not display. Do not proceed.**

---

## SECTION D — MARKET CARD LOCK

Guardian permanently locks the Market Universe card structure.

Every card MUST contain all of the following — always:

| Field | Always Required | Required When Prediction Active |
|-------|----------------|--------------------------------|
| Movement (UP / DOWN) | ✅ | ✅ |
| UP Probability | ✅ | ✅ |
| DOWN Probability | ✅ | ✅ |
| Target (Price to Beat) | ✅ | ✅ |
| Gap | ✅ | ✅ |
| Confidence | ✅ | ✅ |
| Countdown | ✅ | ✅ |
| Status | ✅ | ✅ |
| Open At | — | ✅ |
| Coverage | — | ✅ |
| Entries | — | ✅ |

Guardian must compare **Previous Card → New Card** after every change.

If any required field disappears → **FAIL. Roll back immediately.**

---

## SECTION E — REGRESSION SNAPSHOT

Before coding: Guardian records the **Pre-Change Snapshot** — the full set of visible dashboard fields, layout sections, and information items.

After coding: Guardian records the **Post-Change Snapshot**.

Guardian compares:

- Layout sections present
- Typography consistency
- Components rendered
- Information item count

If **information decreases** between snapshots → **FAIL. Roll back.**

The snapshot comparison is mandatory. It may not be skipped even for "minor" changes.

---

## SECTION F — LAYOUT VALIDATOR

Guardian checks the rendered dashboard for all of the following:

- [ ] No element overlaps another element
- [ ] No content is clipped or cut off at any viewport
- [ ] No approved information is hidden (`display:none`, `visibility:hidden`, zero height, overflow:hidden)
- [ ] No duplicated widgets or panels
- [ ] No sections have disappeared
- [ ] Consistent spacing across equivalent components
- [ ] Consistent typography (size, weight, colour) across equivalent components

Result: **PASS / FAIL**

If FAIL → identify the specific element, fix within current phase scope only.

---

## SECTION G — VOCABULARY VALIDATOR

The forbidden word list is permanently active.

Guardian scans every string rendered to the user before and after every change.

**Forbidden words (auto-FAIL if detected in UI):**

```
Trade / Trading / Trader
Broker / Exchange
Order / Orderbook
Bid / Ask / Spread
Margin / Leverage
PnL / P/L / Profit & Loss
Stop Loss / Take Profit
Portfolio
Exposure
Capital
Position
Entry / Exit
Risk/Reward
```

If any forbidden term becomes visible in the UI → **FAIL. Roll back before delivering.**

---

## SECTION H — PHASE ENFORCEMENT

Guardian validates the current phase on every task.

If requested work belongs to a phase that is **LOCKED** → **DENY. No exceptions.**

Only the user can unlock a phase. Guardian enforces this without exception.

Current phase table is maintained in `PHASE_GATE.md`. Guardian reads it on every session.

---

## SECTION I — API LOCK

No new external API integration may begin until:

1. Phase 5 (Data Source Audit) is **complete and approved** by the user.
2. Phase 6 (Polymarket API Integration) is **explicitly unlocked** by the user.

**Current status: LOCKED**

Any new API call appearing in a diff while Phase 5/6 remains locked → **FAIL.**

---

## SECTION J — POST-CODE VALIDATION

After every modification, Guardian automatically executes the full post-code audit:

| Audit | Check | Result |
|-------|-------|--------|
| Regression Audit | All required card fields still present | PASS / FAIL |
| Vocabulary Audit | No forbidden trading terms in rendered UI | PASS / FAIL |
| Source Audit | No new unverified data source introduced | PASS / FAIL |
| Layout Audit | No overlap, clipping, or hidden content | PASS / FAIL |
| UI Audit | No information removed; no uninstructed additions | PASS / FAIL |
| Data Integrity Audit | All values traceable to an approved source | PASS / FAIL |

All six audits must PASS before the task is delivered to the user.

If any audit FAILS → Roll back. Fix. Re-run all six audits.

---

## BOOT ORDER (run before this document)

1. `CONSTITUTION.md`
2. `PROJECT_RULES.md`
3. `DATA_RULES.md`
4. `UI_RULES.md`
5. `PHASE_GATE.md`
6. `replit.md`
7. `.agents/memory/product-constitution.md`
8. ← **THIS FILE** (`AI_GUARDIAN.md`)

---

## PRE-CODE CHECKLIST (Gate 10 — run first, every session)

Before writing a single line of code, output this checklist and verify every item:

| Gate | Check | Result |
|------|-------|--------|
| G1 | Identity valid — project is LIMWANPO AI, Polymarket Intelligence Platform | PASS / FAIL |
| G2 | All displayed values trace to an approved source | PASS / FAIL |
| G3 | All required card fields present — no regression | PASS / FAIL |
| G4 | No forbidden vocabulary in UI | PASS / FAIL |
| G5 | No overlap, clipping, or hidden content | PASS / FAIL |
| G6 | Requested work belongs to current active phase | PASS / FAIL |
| G7 | No information will be removed by this change | PASS / FAIL |
| G8 | No uninstructed new metrics, badges, or widgets will be added | PASS / FAIL |

If ANY gate is FAIL → **STOP. Do not write code. Explain why. Wait for user.**

---

## GATE 1 — IDENTITY VALIDATION

### Verify

- Project Name: **LIMWANPO AI**
- Project Type: **Polymarket Probability Intelligence Platform**

### This project is NOT

- Trading Platform
- Broker
- Exchange
- Order Management System
- Crypto Terminal
- Portfolio Manager

### Rule

If project identity has drifted to any of the above → **STOP immediately.**

Re-read `CONSTITUTION.md`. Correct the identity before continuing.

---

## GATE 2 — SOURCE VALIDATION

### Rule

Before displaying ANY data value, verify its source.

**Allowed sources:**

| Source | Allowed For |
|--------|------------|
| Polymarket CLOB API | UP/DOWN probability, Open At price |
| Polymarket Gamma API | Market metadata, countdown, resolution date, status |
| Binance REST API | Chart candles, BTC/ETH/SOL/XRP reference price, Target (opening price) |
| Chainlink | Oracle/reference price (chart context only) |
| Internal Engine Calculation | Confidence, Gap, AI Activity, System Health, Pipeline state, Budget |

**Forbidden sources:**

- Placeholder / hardcoded string
- `Math.random()` or generated value
- Estimated / simulated value
- Unknown origin
- Any source not listed above

If source is forbidden → **DO NOT DISPLAY. FAIL.**

---

### Permanent Source Table (audited 2026-07-08)

| Dashboard Component | Rendered Element | API Endpoint | Approved Source | Status |
|---------------------|-----------------|--------------|-----------------|--------|
| BTC/ETH/SOL/XRP live price | `#bb-price`, `.asset-live-px` | `GET /api/v1/crypto/ticker` | Binance (chart context) | ✅ APPROVED |
| UP Probability | `.mc-yes-pct` (yesPct) | `GET /api/v1/price/active` | Polymarket CLOB (mid-point) | ✅ APPROVED |
| DOWN Probability | `.mc-no-pct` (noPct) | `GET /api/v1/price/active` | Polymarket CLOB (mid-point) | ✅ APPROVED |
| Target (Price to Beat) | `.mc-ptb-v-main` | `GET /api/v1/universe/active` → `market.opening_price` | Binance candle at market start | ✅ APPROVED |
| Gap | `gapFmt` (JS calculation) | Derived from live price minus Target | Internal calculation | ✅ APPROVED |
| Confidence | `.mc-conf-val` | `GET /api/v1/signals/latest` or `/opportunities` | Internal Signal/Opportunity Engine | ✅ APPROVED |
| Countdown | `.mc-cd` | `GET /api/v1/universe/active` → `market.end_time` | Polymarket Gamma | ✅ APPROVED |
| Status badge | `.mc-stxt` | `GET /api/v1/universe/active` → `market.status` | Polymarket Gamma | ✅ APPROVED |
| Budget / Available | `#p-capital`, `#p-avail` | `GET /api/v1/portfolio/summary` | Internal engine (settings baseline) | ✅ APPROVED |
| Coverage | `#p-used` | `GET /api/v1/positions/open` | Internal engine | ✅ APPROVED |
| Entries (prediction count) | `#p-open` | `GET /api/v1/positions/open` | Internal engine | ✅ APPROVED |
| Open At | `.mc-ptb-v` (EntryPct) | `GET /api/v1/positions/open` → `pos.open_price` | Internal engine (price at prediction open) | ✅ APPROVED |
| AI Activity Feed | `#feed-ai` | Internal event polling | Internal engine logs | ✅ APPROVED |
| System Health | `.hlth-pct` | `GET /api/v1/health/detailed` | Internal engine heartbeats | ✅ APPROVED |
| Prediction Pipeline stages | `#pipe-inner` | `GET /api/v1/analytics/performance` | Internal engine state | ✅ APPROVED |
| BTC Chart candles | Canvas chart | `GET /api/v1/btc-candles` | Binance (chart context only) | ✅ APPROVED |

> **Phase 5 resolution (2026-07-08):** `Confidence` was investigated and confirmed to be a real deterministic calculation (`compute_confidence()`), not hardcoded — uniform values are expected AMM-init-phase behavior, not a defect. `Budget` was re-wired from a hardcoded JS constant to `GET /api/v1/portfolio/summary` → `initial_capital` (sourced from `settings.CAPITAL_INITIAL_USDC`). See `SOURCE_AUDIT.md` Phase 5 remediation section.

---

## GATE 3 — MARKET CARD REGRESSION

### Mandatory fields — must always be present on every prediction card

| Field | Required Always | Required When Prediction Active |
|-------|----------------|--------------------------------|
| Movement (UP / DOWN label) | ✅ | ✅ |
| UP Probability | ✅ | ✅ |
| DOWN Probability | ✅ | ✅ |
| Target (Price to Beat) | ✅ | ✅ |
| Gap | ✅ | ✅ |
| Confidence | ✅ | ✅ |
| Countdown | ✅ | ✅ |
| Status | ✅ | ✅ |
| Open At | — | ✅ |
| Coverage | — | ✅ |
| Entries | — | ✅ |

### Rule

Before saving any UI change, verify every item in the table above is still visible.

If any item disappears → **FAIL. Roll back immediately.**

---

## GATE 4 — FORBIDDEN VOCABULARY

### Permanently forbidden words in all UI-rendered text

```
Trade / Trading / Trader
Broker / Exchange
Order / Orderbook
Bid / Ask / Spread
Margin / Leverage
PnL / P/L
Stop Loss / Take Profit
Portfolio
Exposure
Capital
Position
Entry / Exit
Risk/Reward
```

### Rule

Scan every string rendered to the user.

If any forbidden word is detected → **FAIL. Remove before proceeding.**

### Approved replacements (Constitution terminology)

| Forbidden | Use Instead |
|-----------|------------|
| Position | Prediction |
| Portfolio | Prediction Workspace |
| Exposure | Coverage |
| Capital | Budget |
| Entry | Open At |
| Exit | Resolution |
| Orderbook | Order Flow |
| P/L / PnL | Outcome |

---

## GATE 5 — UI VALIDATION

### Verify all of the following

- [ ] No element overlaps another element
- [ ] No content is clipped or cut off
- [ ] No approved information is hidden (`display:none`, zero height, overflow hidden)
- [ ] No duplicated information on screen
- [ ] No unnecessary whitespace gaps
- [ ] Consistent spacing across equivalent components
- [ ] Consistent typography (font size, weight, colour) across equivalent components

### Result: PASS / FAIL

If FAIL → identify the specific element and fix within Phase 3 scope.

---

## GATE 6 — PHASE VALIDATION

### Rule

Read `PHASE_GATE.md` before every task.

Confirm the requested work belongs to the **currently active phase**.

| Phase | Status |
|-------|--------|
| Phase 1 — Identity Lock | ✅ COMPLETE |
| Phase 2 — Vocabulary Lock | ✅ COMPLETE |
| Phase 3 — UI Stabilization | ✅ COMPLETE |
| Phase 4 — Regression Lock | ✅ COMPLETE |
| Phase 5 — Data Source Audit | ✅ COMPLETE (2026-07-08) |
| Phase 6 — Polymarket API Integration | ✅ COMPLETE (2026-07-08) |
| Phase 7 — Historical Database | 🔄 **ACTIVE** |
| Phase 8 — Prediction Engine | 🔒 LOCKED |
| Phase 9 — Outcome Learning | 🔒 LOCKED |
| Phase 10 — Optimization | 🔒 LOCKED |

See `PHASE_GATE.md` for the authoritative roadmap and per-phase requirements.

If requested work belongs to a locked phase → **STOP. Explain. Wait for user approval.**

---

## GATE 7 — DATA LOSS CHECK

### Rule

Before saving any code change, compare old UI vs new UI.

If the count of visible information items **decreases** → **FAIL. Roll back.**

Zero tolerance for silent removal of approved content.

---

## GATE 8 — NEW INFORMATION CHECK

### Rule

AI may NOT invent or add:

- New metrics
- New indicators
- New badges
- New widgets
- New terminology
- New layout panels

Unless the user **explicitly requests** the addition.

"There is empty space" is NOT a reason to add content.

If uninstructed new content is present → **FAIL. Remove before proceeding.**

---

## GATE 9 — API INTEGRATION LOCK

### Rule

Do NOT integrate any new external API until Phase 5 (Data Source Audit) is complete and Phase 6 is unlocked by the user.

Current status: **UNLOCKED (2026-07-08)** — Phase 5 complete, Phase 6 active per `PHASE_GATE.md`.
Within Phase 6, new Polymarket API surface (CLOB/Gamma) may be integrated. A brand-new
non-Polymarket external provider (e.g. a news/sentiment API) still requires explicit
owner approval per the Autonomous Decision Layer's "new external provider" stop
condition, even while Phase 6 is active.

Any new API call found in a diff when Phase 6 has not been approved → **FAIL.**

---

## GATE 10 — PRE-CODE CHECKLIST

*(Reproduced at top of document for fast access)*

Run before writing any code. All gates must PASS.

---

## GATE 11 — POST-CODE CHECKLIST

Run after completing every code change. All audits must PASS before delivering.

| Audit | Check | Result |
|-------|-------|--------|
| Regression Audit | All required card fields still present | PASS / FAIL |
| Source Audit | No new unverified data source introduced | PASS / FAIL |
| Vocabulary Audit | No forbidden trading terms in rendered UI | PASS / FAIL |
| Layout Audit | No overlap, clipping, or hidden content | PASS / FAIL |
| UI Audit | No information removed, no uninstructed additions | PASS / FAIL |

If any audit FAILS → **Roll back. Fix. Re-run all audits.**

---

## PERMANENT MEMORY

- Never ask "What project is this?"
- Never assume trading terminology.
- Never replace Polymarket data with external trading data.
- Never redesign without explicit approval.
- Never skip a phase.
- This Guardian system is permanent and applies to every future session and every AI model.

---

*Last updated: 2026-07-09 | Phase 7 — Historical Database | ACTIVE*
