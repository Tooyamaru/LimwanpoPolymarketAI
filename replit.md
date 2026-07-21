# LIMWANPO AI — Polymarket Probability Intelligence Terminal

> **Before editing anything, read `CONSTITUTION.md` and `MASTER_OPERATING_PROMPT.md` at the project root. They permanently override all assumptions and define the agent's operating rules (including the Autonomous Decision Layer governing when to act vs. ask).**

## Project Identity

This is a professional **Polymarket Probability Intelligence Terminal**.

Its sole purpose is to analyze, monitor, compare, score, and predict probabilities from Polymarket prediction markets.

This is NOT a trading app. NOT an exchange terminal. NOT an order execution platform. NOT a portfolio manager.

Every design decision must answer: *"Does this improve probability analysis?"*

## Architecture: Single Application

There is only **one** application in this repository: `backend/`, served by a single `Start application` workflow on a single port (5000). There is no second app, no sandbox, and no secondary server. The Mockup Sandbox has been permanently retired (2026-07-08) — see `AI_GUARDIAN.md` and `PROJECT_RULES.md`. Future work must never recreate a second application or workflow.

## Stack

- **Backend**: FastAPI + Uvicorn (async Python 3.12)
- **Database**: PostgreSQL 16 (Replit managed — `DATABASE_URL` injected automatically)
- **Cache / heartbeats**: Redis (in-process `redis-server` on port 6379, internal only)
- **External APIs**: Binance (chart candles — context only), Polymarket Gamma API, Polymarket CLOB

## How to run

The **Start application** workflow handles everything:
```
pip install -q -r backend/requirements.txt
nix-shell -p redis --run "redis-server --daemonize yes --port 6379 --loglevel warning"
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

The dashboard is served at port 5000 (→ external port 80).

### Environment notes (2026-07-10 re-import)
- `redis` is declared in `replit.nix` but isn't on the default shell `PATH` in this container, so the workflow launches it via `nix-shell -p redis --run "redis-server ..."` — do not revert to a bare `redis-server` call.
- If Gamma/Binance/CLOB requests fail with `CERTIFICATE_VERIFY_FAILED`, the `certifi` pip package's CA bundle file is missing/corrupted post-import; fix with `pip install --force-reinstall --no-cache-dir certifi`.

## AI Engine Pipeline (Layers 1–11)

| Layer | Name | Role |
|-------|------|------|
| 1 | Collector | Fetches Polymarket market data |
| 2 | Scanner | Identifies candidate markets |
| 3 | Universe / Price refresh | Maintains live market universe |
| 4 | Signal Engine | Detects probability movement signals |
| 5 | Opportunity Engine | Scores market opportunities |
| 6 | Strategy Engine (Recommendation Engine) | Selects best predictions |
| 7–8 | Prediction Tracking (formerly Execution/Position) | Records AI predictions |
| 9 | Risk Engine | Validates prediction quality |
| 10 | Portfolio Reporting (Prediction Workspace) | Summarises prediction outcomes |
| 11 | Resolution Monitor (formerly Exit Engine) | Monitors market resolution |

## Dependencies

Python packages installed via `pip install -r backend/requirements.txt`.

## Setup Verification (2026-07-21 re-import)

- `postgresql-16` module was missing from `.replit` `modules` after this re-import (same recurring pattern as prior imports); restored via `installProgrammingLanguage`.
- Workflow restarted cleanly after the fix; dashboard renders live at port 5000 — 8 engines active, 1 market loaded, BTC/ETH/SOL/XRP price feeds operational (confirmed via screenshot).
- No secrets required; Polymarket CLOB and Binance APIs are public; `DATABASE_URL` injected automatically by Replit managed Postgres.

## Setup Verification (2026-07-17 re-import)

- Workflow restarted cleanly after re-import; `checkDatabase` confirms Postgres provisioned and ready.
- Dashboard renders live at port 5000 — 8 engines active, 3 markets loaded, BTC/ETH/SOL/XRP price feeds operational (confirmed via screenshot).
- No secrets required; Polymarket CLOB and Binance APIs are public; `DATABASE_URL` injected automatically by Replit managed Postgres.
- Redis started in-workflow via `nix-shell -p redis --run "redis-server --daemonize yes ..."` — do not revert to bare `redis-server`.
- Untracked file `attached_assets/Pasted-*.txt` present from import; not part of the application.

## Setup Verification (2026-07-13 re-import)

- `.replit` `modules` was missing `postgresql-16` after this re-import (dropped in a prior commit); restored it so the Replit-managed Postgres integration stays wired up alongside the `postgresql` nix package already used for the client libs.
- Verified end-to-end after the fix: workflow restarted cleanly, `checkDatabase` reports the Postgres database as provisioned and ready, and the dashboard renders live data — 12 markets, 8 engines nominal, signals/opportunities/predictions all populating (confirmed via screenshot of `/`).
- No secrets were needed to start; Polymarket/Binance/CLOB access is public and `DATABASE_URL`/`REDIS_URL` are already wired through Replit's managed Postgres and the in-workflow Redis start command.

## Setup Verification (2026-07-08)

- **Main app**: Running on port 5000 — all 9 engines active, 12 Polymarket markets live, dashboard rendering correctly.
- **Redis**: Started in-process via `redis-server --daemonize yes --port 6379`.
- **PostgreSQL**: Managed by Replit — `DATABASE_URL` injected automatically; schema initialised on first startup.
- **No external secrets required** to start in development mode — Polymarket CLOB and Binance APIs are public; paper-trading mode is the default.
- **Mockup Sandbox retired (2026-07-08)**: `artifacts/mockup-sandbox/` and its workflow have been permanently removed. There is now only one workflow, one port, and one application.

## User Preferences

- Python 3.12
- Structured JSON logging via structlog
- Async SQLAlchemy with asyncpg driver
- Keep Docker/docker-compose files but don't rely on them for running in Replit
- Redis is internal-only — never expose port 6379 externally
- Pydantic v2 `serialization_alias` + `ConfigDict(populate_by_name=True)` for API field renaming (no DB changes)
- Vocabulary: prediction market terminology only — see `CONSTITUTION.md` and `.agents/memory/product-constitution.md`
