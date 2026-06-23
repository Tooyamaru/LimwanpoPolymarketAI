# AUDIT REPORT — Polymarket Quant Bot
**Date:** 2026-06-23  
**Scope:** backend/app/ — Layers 1–8  
**Auditor:** Automated full-codebase review

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 4     |
| MEDIUM   | 12    |
| LOW      | 8     |
| INFO     | 6     |

---

## HIGH Severity

### AUD-H01 — Repository files in wrong package
**Affected:** `backend/app/services/*_repository.py` (10 files)  
**Issue:** Repository files (pure DB query layer) live inside `services/`, violating separation of concerns. Business logic and data access are co-located.  
**Recommendation:** Move all `*_repository.py` files to a dedicated `backend/app/repositories/` package and update all consumer imports.

### AUD-H02 — Background worker loops embedded in main.py
**Affected:** `backend/app/main.py` (507 lines)  
**Issue:** All 8 background loop coroutines (`_run_scanner_loop`, `_run_price_refresh_loop`, etc.) are defined inside `main.py`, making it impossible to test, reuse, or reason about workers independently.  
**Recommendation:** Extract all worker functions to `backend/app/workers/engine_workers.py`.

### AUD-H03 — Dead code: `binance_futures.py`
**Affected:** `backend/app/collector/binance_futures.py`  
**Issue:** `BinanceFuturesCollector` raises `NotImplementedError` on every method. It is never imported or used anywhere in the codebase. Its docstring in `collector/__init__.py` still references it as a live component.  
**Recommendation:** Remove file. Update `collector/__init__.py` docstring.

### AUD-H04 — Execution Engine queries PENDING status — bypasses future Risk Engine
**Affected:** `backend/app/services/execution_engine.py:55`  
**Issue:** `ExecutionEngine` queries `TradeDecision.status == "PENDING"` directly. When a Risk Engine is added, there is no gate between strategy decisions and order execution. Any PENDING decision gets executed without risk screening.  
**Recommendation:** Add `RISK_APPROVED` status. Risk Engine transitions PENDING → RISK_APPROVED or BLOCKED. Execution Engine queries RISK_APPROVED only.

---

## MEDIUM Severity

### AUD-M01 — Pydantic response schemas embedded in API routers
**Affected:** All `api/v1/*.py` files  
**Issue:** Response schemas (e.g., `PositionResponse`, `OrderResponse`) are defined inline in the router files, making them unreusable and scattered.  
**Recommendation:** Create `backend/app/schemas/` package with per-domain schema files.

### AUD-M02 — Hardcoded scoring constants in opportunity engine
**Affected:** `backend/app/services/opportunity_engine.py`  
**Issue:** Scoring thresholds (`600.0`, `2000.0`, `MID_MOVE_THRESHOLD=0.001`) are magic numbers hardcoded in the engine body. Changes require a code deployment.  
**Recommendation:** Move all scoring constants to `settings.py` or a `config/scoring.py` module.

### AUD-M03 — `market_snapshot.py` is a legacy model (superseded by `market_price_snapshot.py`)
**Affected:** `backend/app/models/market_snapshot.py`, `backend/app/services/market_repository.py`  
**Issue:** `MarketSnapshot` (Layer 1 collector) and `MarketPriceSnapshot` (Layer 3 CLOB) both exist. The system now uses `MarketPriceSnapshot` exclusively for price tracking. `MarketSnapshot` is populated but never queried by any engine.  
**Recommendation:** Deprecation candidate. Remove `market_snapshot.py` model and `save_snapshot`/`get_latest_snapshots` from `market_repository.py` after confirming no downstream consumers.

### AUD-M04 — Duplicate price-parsing logic
**Affected:** `backend/app/services/market_discovery.py`, `backend/app/services/clob_client.py`  
**Issue:** Token price parsing (splitting `clobTokenIds`, extracting YES/NO token IDs) appears in both files with slight variations.  
**Recommendation:** Extract to `backend/app/utils/market_utils.py`.

### AUD-M05 — Session factory boilerplate repeated in main.py (~8×)
**Affected:** `backend/app/main.py`  
**Issue:** Every `_run_*_loop` function duplicates the same `get_session_factory()` / `async with factory() as session` pattern.  
**Recommendation:** Extract to a utility coroutine `workers/base.py: run_with_session(service_fn)`.

### AUD-M06 — Missing foreign key constraints in database
**Affected:** `positions.order_id`, `orders.decision_id`, `risk_events.decision_id`  
**Issue:** SQLAlchemy models define `order_id` (Integer) on `positions` but there is no FK constraint declared — only an index. Referential integrity is not enforced at the DB level.  
**Recommendation:** Add `ForeignKey("orders.id")` and `ForeignKey("trade_decisions.id")` to affected models.

### AUD-M07 — No retry logic for 429 rate-limit errors from Polymarket CLOB
**Affected:** `backend/app/services/clob_client.py`, `backend/app/services/gamma_series_client.py`  
**Issue:** Both clients have a generic `MAX_RETRIES=3` retry with exponential backoff, but they do NOT distinguish 429 (rate limit) from 500 (server error). 429 should use a longer backoff.  
**Recommendation:** Check response status codes before retry; use `Retry-After` header when present.

### AUD-M08 — `source_validator.py` and `source_validation_result.py` unused in active layers
**Affected:** `backend/app/services/source_validator.py`, `backend/app/models/source_validation_result.py`, `backend/app/api/v1/source_validation.py`  
**Issue:** Source validation was a Sprint 5 investigative tool. It is not called by any background loop or engine in the active pipeline.  
**Recommendation:** Keep as-is (audit tooling), but annotate clearly as a diagnostic/audit module, not a production pipeline component.

### AUD-M09 — `collector/` imports `market_repository` directly (crosses layer boundary)
**Affected:** `backend/app/collector/scheduler.py:14–17`  
**Issue:** The Collector (data ingestion) imports directly from `market_repository` (business layer). This creates tight coupling between ingestion and persistence.  
**Recommendation:** Keep for now — this is acceptable in current architecture; document the coupling explicitly.

### AUD-M10 — No `utils/` package
**Affected:** Entire codebase  
**Issue:** Common utilities (date helpers, rounding, price math) are duplicated ad-hoc across files.  
**Recommendation:** Create `backend/app/utils/__init__.py`.

### AUD-M11 — Strategy Engine SKIP decisions not persisted but silently discarded
**Affected:** `backend/app/services/strategy_engine.py:125`  
**Issue:** `STRATEGY_PERSIST_SKIPS=False` causes all SKIP decisions (which are the majority in AMM init phase) to be silently dropped. There is no observability into why decisions are being skipped.  
**Recommendation:** Add a counter/metric log showing skip reason breakdown even when not persisting rows.

### AUD-M12 — Position bulk update uses N individual UPDATE statements
**Affected:** `backend/app/services/position_service.py`  
**Issue:** `recalculate_pnl()` loops over all OPEN positions and executes one UPDATE per position. With 100+ positions this becomes N round-trips.  
**Recommendation:** Refactor to a single `UPDATE positions SET unrealized_pnl = quantity * (current_price - entry_price) WHERE status = 'OPEN' AND current_price IS NOT NULL`.

---

## LOW Severity

### AUD-L01 — Inline imports inside loop functions in main.py
**Affected:** `backend/app/main.py` (lines 62, 99, 134+)  
**Issue:** Service imports (e.g., `from app.services.execution_engine import ExecutionEngine`) are done inside async functions rather than at module top-level. While this avoids circular import issues, it makes dependency tracking harder.  
**Recommendation:** Resolve any circular import issues at the module level; move imports to top of file.

### AUD-L02 — Missing `__all__` exports in `services/__init__.py`
**Affected:** `backend/app/services/__init__.py`  
**Issue:** Empty `__init__.py` — no explicit public API defined for the services package.  
**Recommendation:** Add `__all__` listing the public service classes.

### AUD-L03 — `chainlink.py` is a stub with no implementation
**Affected:** `backend/app/collector/chainlink.py`  
**Issue:** File exists but contains only a placeholder. Never imported anywhere.  
**Recommendation:** Remove or clearly mark as `# FUTURE: Chainlink oracle integration`.

### AUD-L04 — Inconsistent logging field names
**Affected:** Various services  
**Issue:** Some log calls use `asset=` and `timeframe=`, others use `symbol=` and `tf=`. Inconsistent field names make log aggregation harder.  
**Recommendation:** Standardize: always use `asset=`, `timeframe=`, `condition_id=` (truncated to 12 chars).

### AUD-L05 — No docstrings on repository functions in `position_repository.py`
**Affected:** `backend/app/services/position_repository.py`  
**Issue:** Most functions lack docstrings. All other repository files have them.  
**Recommendation:** Add one-line docstrings to all public functions.

### AUD-L06 — `market.py` model has no `condition_id` column
**Affected:** `backend/app/models/market.py`  
**Issue:** The primary CLOB identifier (`condition_id`) is not on the `Market` model (Layer 1). Cross-layer joins require going through `market_universe` instead.  
**Recommendation:** Noted as architectural decision; document explicitly.

### AUD-L07 — `event_classifier.py` and `event_classification_repository.py` tightly coupled
**Affected:** `backend/app/services/event_classifier.py`  
**Issue:** Classifier directly calls the repository instead of returning results to a service layer that persists them. This makes unit testing the classifier without DB difficult.  
**Recommendation:** Separate classification logic from persistence — classifier returns results, service persists.

### AUD-L08 — Missing type hints on some functions
**Affected:** Various services  
**Issue:** Several functions in `market_discovery.py` and `source_validator.py` lack return type annotations.  
**Recommendation:** Add return type hints throughout.

---

## INFO

### AUD-I01 — `APP_VERSION` env override in .replit sets v0.4.0 but code defaults to v0.6.0
**Recommendation:** Keep env override during development to avoid accidental version bumps; document the versioning strategy.

### AUD-I02 — Redis is used only for health check — no actual caching
**Recommendation:** Confirm Redis will be used in Layer 9+ (e.g., rate-limiting); otherwise document its current role as "health indicator only".

### AUD-I03 — No migration tool (Alembic is installed but unused)
**Recommendation:** Either use Alembic for schema migrations or document the current `ADD COLUMN IF NOT EXISTS` startup migration strategy as the intended approach.

### AUD-I04 — 86 test files exist but tests import from `services.*_repository` (will break after refactor)
**Recommendation:** Update test imports after repository move.

### AUD-I05 — `pyproject.toml` at root is the Replit default, not the project's `backend/pyproject.toml`
**Recommendation:** Keep as-is; document that `backend/requirements.txt` is the authoritative dependency list.

### AUD-I06 — Paper mode quantity hardcoded to 1.0 in `execution_engine.py`
**Recommendation:** Move to `settings.py` as `EXECUTION_DEFAULT_QUANTITY`.

---

*Generated by automated audit — 2026-06-23*
