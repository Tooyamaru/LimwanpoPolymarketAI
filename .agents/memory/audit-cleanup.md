---
name: Audit cleanup 2026-06-23
description: What was found and fixed in the full codebase audit; rules that must stay consistent going forward.
---

## Rule: No inline schemas in routers
All API routers must import from `app.schemas.*`. Defining `class Foo(BaseModel)` directly in an `api/v1/*.py` file is forbidden.

**Why:** The refactor established `schemas/` as the single source of truth for Pydantic response models. Inline schemas in routers bypass this and scatter the schema surface area.

**How to apply:** When adding any new endpoint with a new response shape, create or extend a file in `backend/app/schemas/` first, then import it in the router.

## schemas/ coverage (14 files, authoritative as of 2026-06-23)
`classifier`, `discovery`, `health`, `market`, `opportunity`, `order`, `position`, `price`, `risk`, `scanner`, `signal`, `source_validation`, `strategy`, `universe`

## Rule: Version must be 0.9.0 in three places
- `backend/app/config/settings.py` → `APP_VERSION = "0.9.0"`
- Replit shared env var `APP_VERSION = "0.9.0"` (set via setEnvVars)
- Root `pyproject.toml` version field

**Why:** Previous audit found three divergent values (0.6.0, 0.7.0, 0.4.0). Canonical version is the count of complete layers (L1–L9 = 0.9.0).

## Rule: TradeDecision.status lifecycle
Correct lifecycle comment in `models/trade_decision.py`:
```
PENDING → RISK_APPROVED → EXECUTED   (normal path)
PENDING → BLOCKED                    (risk rule tripped)
```
The old text `PENDING → EXECUTED | CANCELLED | EXPIRED` predates Layer 9 and must not reappear.
