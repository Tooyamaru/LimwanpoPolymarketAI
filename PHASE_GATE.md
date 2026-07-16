# LIMWANPO AI — PHASE GATE (PERMANENT)

## Source
Derived from permanent project initialization document and Phase Gate System.

---

## Rules

- This project is PHASE-driven, not feature-driven.
- Phases may NOT be skipped.
- Only the project owner (user) decides phase transitions.
- The agent does NOT decide the next phase.
- Even if another phase appears beneficial, remain inside the approved phase.

---

## Current Roadmap

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| 1 | Identity Lock | Ensure permanent project identity as LIMWANPO AI | ✅ COMPLETE |
| 2 | Vocabulary Lock | Remove every trading term; replace with Constitution terminology | ✅ COMPLETE |
| 3 | UI Stabilization | Stabilize layout — no overlap, no clipping, no hidden/deleted/added info | ✅ COMPLETE |
| 4 | Regression Lock | Protect approved UI; enforce regression checklist before every change | ✅ COMPLETE |
| 5 | Data Source Audit | Audit every visible value; verify data lineage for each | ✅ COMPLETE (2026-07-08 — see SOURCE_AUDIT.md remediation) |
| 6 | Polymarket API Integration | Replace every placeholder with official Polymarket data | ✅ COMPLETE (2026-07-08) |
| 7 | Historical Database | Store prediction history; database only, no UI changes | 🔄 ACTIVE |
| 8 | Prediction Engine | Improve prediction quality using historical data | 🔒 LOCKED |
| 9 | Outcome Learning | AI learns from resolved Polymarket markets | 🔒 LOCKED |
| 10 | Optimization | Performance, refactoring, speed, memory | 🔒 LOCKED |

**Reconciliation note (2026-07-08):** Phases 3–5 were completed and verified across prior
sessions (UI stabilization, regression discipline maintained since, and the Phase 5
Source Stabilization remediation documented in SOURCE_AUDIT.md) before this roadmap
file was updated to reflect it. The project owner approved marking them complete and
unlocking Phase 6 on this date.

**Phase 6 closure (2026-07-08):** Verified in `SOURCE_AUDIT.md` — zero remaining
Polymarket-data placeholders anywhere in the dashboard. The one deferred stub (News
Engine) is explicitly out of Phase 6 scope (macro/news context, not Polymarket data)
and remains parked per owner decision — see "Deferred Modules" below. Owner approved
marking Phase 6 complete and unlocking Phase 7 on this date.

---

## Phase 3 — UI Stabilization (✅ COMPLETE)

Requirements met:

- No overlap between any UI elements
- No clipping of any content
- No hidden information
- No deleted information
- No added information (layout refinement only)

## Phase 4 — Regression Lock (✅ COMPLETE)

Requirement met: every subsequent change (through and including Phase 5) was validated
against the approved UI before merge — no unapproved layout/vocabulary regressions.

## Phase 5 — Data Source Audit (✅ COMPLETE)

Requirement met: every visible value traced to exactly one approved source
(Polymarket CLOB/Gamma, internal engine calc, internal DB, config, or Binance for the
BTC chart exception). See `SOURCE_AUDIT.md` for the full field-by-field lineage table
and the 2026-07-08 remediation of all FAIL items.

## Phase 6 — Polymarket API Integration (✅ COMPLETE)

Goal met: every card/panel value verified backed by a live Polymarket CLOB/Gamma call
or a real internal calculation derived from one. See `SOURCE_AUDIT.md` Phase 6
verification section. No new UI elements, no redesign performed.

## Phase 7 — Historical Database (🔄 ACTIVE)

Goal: store prediction history, close the self-learning feedback loop, and improve
prediction quality using historical data — database and engine work only, no UI
changes.

Requirements for Phase 7 completion:

- Historical prediction/outcome data durably stored and queryable (largely already in
  place — `outcome_learnings`, `engine_performance_stats`, `engine_weights`,
  `market_price_snapshots`, `decision_logs` — verify completeness and close any gaps)
- Self-learning feedback loop actually closes: live decision-making reads back from
  historical outcome/calibration data, not just one-directional logging
- No new external providers introduced (per owner instruction 2026-07-08 — internal
  DB/engine work only)
- No UI changes

**DO NOT leave Phase 7 until explicitly approved by the user.**

---

## Deferred Modules

### News Engine (macro/news sentiment)

- **Status:** Deferred — optional future module, per owner decision 2026-07-09.
- Currently always returns NEUTRAL / confidence 0 (stub in `app/services/news_engine.py`).
- Constitution allows macro/news providers as optional contextual source; no external
  provider may be added without explicit future owner approval.
- Not required for Phase 7. Do not revisit unless the owner explicitly requests it.

---

## Decision Rule

Before proposing ANY work, ask: **"What phase am I currently inside?"**

If the proposed task belongs to another phase: STOP. Do not continue.

---

## Forbidden at All Times

- "Let's also…"
- "I'll improve…"
- "I noticed…"
- Installing packages unless requested
- Redesigning UI
- Renaming components
- Reorganizing dashboard
- Adding new cards
- Removing information
- Adding information because "there is empty space"
- Creating features outside the current phase

---

## After Every Task — Required Report

```
Current Phase:     Phase 7 — Historical Database
Task Completed:    [description]
Regression Check:  PASS / FAIL
Approved For Next Phase?  YES / NO
```
