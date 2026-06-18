---
name: Sprint 4 discovery_runs schema migration
description: How Sprint 4 classification count columns were added to the pre-existing discovery_runs table without Alembic
---

`discovery_runs` was created in Sprint 3. Sprint 4 added five INTEGER columns (`updown_count`, `price_range_count`, `news_event_count`, `politics_count`, `other_count`). Because SQLAlchemy `create_all` only creates missing tables (not missing columns), the new columns had to be added via `ALTER TABLE … ADD COLUMN IF NOT EXISTS` in `init_db()` in `core/database.py`.

**Why:** The project has no Alembic migrations; additive DDL in `init_db()` is the agreed pattern for schema evolution. `IF NOT EXISTS` makes it idempotent.

**How to apply:** For any future column additions to existing tables, add an `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statement to the `sprint4_migrations` list (or a new list) inside `init_db()`. Never use DROP TABLE to fix missing columns in production-like environments.
