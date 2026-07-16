---
name: Audit report drift across phases
description: How to keep a multi-phase audit report internally consistent when earlier findings get fixed by later phases
---

When a long-lived audit report (e.g. AI_DECISION_INTEGRITY_AUDIT.md) documents a finding in an early phase and a later phase fixes it, the early phase's prose must be explicitly rewritten as historical/superseded (with a pointer to the phase that resolved it) — not left as if it still describes current code. A reviewer will fail the report on this basis even if the underlying code fix is correct and complete.

**Why:** Multiple sections (main narrative, remaining-risks list, search-classification table) tend to describe the same finding independently; fixing one and leaving the others stale creates internal contradictions that read as the report not matching the code.

**How to apply:** After any code fix during an audit, grep the whole report for every place the old behavior is mentioned (not just the primary section) and mark each one `~~struck through~~` / `RESOLVED in Phase X` with a pointer, rather than deleting — preserves audit trail while staying accurate. Also: when a hard-trace section is redone with real per-row values, make sure the per-market subsections are structurally uniform (no summary table mixed with stage-by-stage tables) and never quote the banned paraphrase words ("implied", "same pattern", "mirrored") even meta-referentially when explaining what was fixed.
