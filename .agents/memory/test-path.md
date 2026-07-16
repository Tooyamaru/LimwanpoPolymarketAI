---
name: Test directory location
description: The pytest test suite lives at backend/app/tests/, not backend/tests/
---

Run tests with: `cd backend && python -m pytest app/tests/ -q`

**Why:** Tests were placed under `app/` alongside the application code from the start; there is no top-level `backend/tests/` directory.
