---
name: Exit Engine design
description: Minimal Exit Decision Engine (Layer 11) — architecture, trigger priority, price rules, and pipeline placement
---

# Exit Engine (Layer 11)

## Files touched
- `backend/app/services/exit_engine.py` — new, ~220 lines
- `backend/app/services/risk_engine.py` — Pass 2: CLOSE_POSITION auto-approve (no rules)
- `backend/app/services/execution_engine.py` — `_execute_close_decision()` added; `run()` handles both entry and exit paths
- `backend/app/workers/engine_workers.py` — `run_exit_engine_loop()` added
- `backend/app/main.py` — `exit_task` registered between opportunity and strategy tasks
- `backend/app/config/settings.py` — 7 EXIT_ENGINE_* settings (ENABLED, INTERVAL_SECONDS, EXPIRY thresholds, STOP_LOSS, PROFIT_TARGET)
- `backend/app/models/trade_decision.py` — `target_position_id: Optional[int]`, `exit_reason: Optional[str]` columns

## Trigger priority (evaluated in order, first match wins)
1. EXPIRY_EXIT — hard: end_date < now+5m; soft: end_date < now+15m AND unrealised_pnl_pct > 0
2. STOP_LOSS — unrealised_pnl_pct ≤ -0.15
3. PROFIT_TARGET — unrealised_pnl_pct ≥ +0.10
4. SIGNAL_INVALIDATION — signal_count_1h == 0 AND position age > 30 min

## Exit price rules (never mid)
- LONG_YES → `yes_bid` from fresh Opportunity row
- LONG_NO  → `1 - yes_ask` from fresh Opportunity row
- If bid unavailable: skip the decision (retry next cycle), do NOT fail

## Duplicate-close protection
ExitEngine calls `_get_pending_exit_position_ids()` which queries trade_decisions
WHERE decision='CLOSE_POSITION' AND status IN ('PENDING','RISK_APPROVED') AND target_position_id IN (current open pos IDs).
Positions with a pending exit are excluded from evaluation.

## Pipeline placement
AFTER run_opportunity_engine_loop, BEFORE run_strategy_engine_loop.

**Why:** Exit engine needs fresh bid prices from the opportunity row; must fire before strategy creates new entry decisions.

## How to apply
Any new exit trigger or price rule must respect the priority order and the bid-only price contract.
Risk engine Pass 2 must remain a blanket auto-approve with no rules (exit decisions bypass all entry risk checks).
