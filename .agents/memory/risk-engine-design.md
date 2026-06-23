---
name: Risk Engine design
description: Layer 9 Risk Engine gates TradeDecisions before Execution Engine; PENDING→RISK_APPROVED|BLOCKED
---

**Rule:** Execution Engine only processes `status == "RISK_APPROVED"` decisions, never `PENDING`.

**Why:** Without risk gating, the Execution Engine executes every Strategy Engine decision immediately with no portfolio constraints.

**How to apply:**
- Pipeline: Strategy (PENDING) → Risk Engine (every 15s) → Execution Engine (every 30s)
- `execution_engine.py` queries `TradeDecision.status == "RISK_APPROVED"`
- Risk Engine updates `td.status` to `"RISK_APPROVED"` or `"BLOCKED"` and appends `RiskEvent`
- Status lifecycle: `PENDING → RISK_APPROVED → EXECUTED` (or `PENDING → BLOCKED`)

**5 rules (first failure wins):**
1. `DUPLICATE_POSITION` — OPEN position with same condition_id exists
2. `MAX_OPEN_POSITIONS` — total OPEN positions ≥ `MAX_OPEN_POSITIONS` (10)
3. `MAX_EXPOSURE` — OPEN for this asset ≥ `MAX_EXPOSURE_PER_ASSET` (3)
4. `DAILY_LOSS` — sum(unrealized_pnl) ≤ `MAX_DAILY_LOSS` (-50.0)
5. `DAILY_TRADES` — orders today ≥ `MAX_DAILY_TRADES` (20)

**Files:** `models/risk_event.py`, `repositories/risk_repository.py`, `services/risk_engine.py`, `api/v1/risk.py`, `workers/engine_workers.py:run_risk_engine_loop`

**Settings:** `RISK_ENGINE_ENABLED`, `RISK_ENGINE_INTERVAL_SECONDS=15`, `MAX_OPEN_POSITIONS`, `MAX_EXPOSURE_PER_ASSET`, `MAX_DAILY_LOSS`, `MAX_DAILY_TRADES`
