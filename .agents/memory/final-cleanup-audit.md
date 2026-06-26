---
name: Final cleanup audit 2026-06-26
description: Project-wide cleanup and architecture audit before AI Engine development. Summary of all changes and known issues.
---

## What was cleaned

**Backend imports removed:**
- `core/database.py` — `from urllib.parse import urlparse`
- `core/redis.py` — `from typing import Optional`
- `repositories/universe_repository.py` — `func` from sqlalchemy import
- `services/market_universe_service.py` — `import asyncio`

**Frontend (index.html) — 1,259 chars removed:**
- 6× `.tgt-score-num.scanner-wait` CSS rules (dead — class no longer applied)
- `.f-tf` CSS rule (dead — span was replaced by Binance ticker)
- `@keyframes cap-fill-anim`, `border-flow`, `score-pop` (dead — never referenced)
- `const renderFeed`, `const renderLiveFeed`, `const renderLeftFeed` legacy aliases (zero call sites)

## Intentionally kept (do not remove)
- `models/__init__.py` and `schemas/__init__.py` re-exports — intentional public API surface and ORM registration
- `from __future__ import annotations` in capital_management_service.py and performance_analytics_service.py
- `toggleHeatmap()` JS function — called via onclick in HTML, not from JS
- 9 duplicate @keyframes in media query blocks — intentional responsive CSS overrides

## Known issues (open)
- 1 browser console "unhandled exception — not an error object" at page load; non-recurring, non-blocking
- Orphaned `discovery_runs` Sprint 4 migration in database.py — no matching ORM model; harmless (savepoint defensive)
- `utils/` is an empty stub — no content yet

## Why: project scored 88/100
- Zero tech-debt markers
- 9-engine pipeline clean and stable
- CORS open (`allow_origins=["*"]`) — acceptable for paper mode only

## Next step
Market Scanner Engine is first in the AI roadmap.
