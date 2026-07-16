---
name: Folder structure refactor
description: repositories/ workers/ schemas/ utils/ created in backend/app/; import paths updated everywhere
---

**Rule:** All DB access goes in `repositories/`, all background loops in `workers/engine_workers.py`, all Pydantic response schemas in `schemas/`.

**Why:** Audit identified that services/ was a catch-all mixing business logic, DB persistence, and background loops — standard separation-of-concerns refactor.

**How to apply:**
- New `*_repository.py` files go in `repositories/` not `services/`
- Import path: `from app.repositories import X_repository as repo`
- New engine loops go in `workers/engine_workers.py` as `run_X_loop(service, universe_ready)` coroutines
- New API schemas go in `schemas/X.py` as `XResponse(BaseModel)` classes
- Routers import schemas: `from app.schemas.X import XResponse, XStatsResponse`
- `main.py` lifespan only imports from workers and instantiates services

**Import update method:** `find backend/app -name "*.py" | xargs sed -i 's/from app\.services import \([a-zA-Z_]*_repository\)/from app.repositories import \1/g'`
