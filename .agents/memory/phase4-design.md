---
name: Phase 4 design decisions
description: Dynamic stop loss, trailing stop, fee simulation, analytics extensions, health trading_metrics block
---

## Dynamic Stop Loss (Part A)
- Formula: threshold = -(position_size_usdc × spread_yes × EXIT_STOP_LOSS_MULTIPLIER=2.5)
- position_size_usdc = quantity × entry_price
- Falls back to static EXIT_STOP_LOSS_USDC=-1.50 when spread_yes is None
- Implemented in `_compute_dynamic_stop_loss()` in exit_engine.py
- Priority 2 (same slot as old static stop); dynamic preferred when spread available
- **Why:** proportional stop prevents large positions from being stopped on noise, and tiny positions from requiring huge losses

## Trailing Stop (Part E)
- Disabled by default: TRAILING_STOP_ENABLED=False; TRAILING_STOP_DISTANCE=0.02
- Only arms when peak_pnl_usdc > 0 (position must have been profitable first)
- Fires when: exit_pnl < (peak_pnl_usdc - position_size_usdc × TRAILING_STOP_DISTANCE)
- Priority 4 (after PROFIT_TARGET at Priority 3)
- peak_pnl_usdc updated in position_service.recalculate_pnl() via max(peak, unrealized_pnl)
- Test note: use exit_pnl < PROFIT_TARGET threshold (0.10) to avoid PROFIT_TARGET firing first in tests
- **Why:** trailing stop must yield to profit target — a profitable position that hit the trailing drawdown is still a win

## Fee Simulation (Part D)
- POLYMARKET_FEE_RATE=0.0 by default (paper mode = no fees)
- entry_fee_usdc = fill_price × quantity × POLYMARKET_FEE_RATE (on Order)
- exit_fee_usdc = exit_price × quantity × POLYMARKET_FEE_RATE (on Order)
- total_fee_usdc on Position = entry_fee + exit_fee; initialized from order.entry_fee_usdc on position open
- realized_pnl = quantity × (exit_price - entry_price) - total_fee_usdc
- New DB columns: orders.entry_fee_usdc, orders.exit_fee_usdc, positions.peak_pnl_usdc, positions.total_fee_usdc

## Analytics Extensions (Part C)
New fields in PerformanceAnalyticsResponse and service output:
- signal_precision = win_rate (every trade is signal-triggered)
- avg_winner_duration_minutes / avg_loser_duration_minutes (split by outcome)
- avg_fee_usdc = mean(total_fee_usdc) across all closed positions
- avg_slippage_usdc = 0.0 always (paper mode)
- avg_time_to_stop_minutes = avg hold time for close_reason="STOP_LOSS"
- avg_time_to_profit_minutes = avg hold time for close_reason="PROFIT_TARGET"

## Health Endpoint (Part G)
- health/detailed now injects AsyncSession via Depends(get_db_session)
- trading_metrics block populated from CapitalManagementService + PerformanceAnalyticsService
- Errors are silenced (try/except + logger.warning); main health status never degraded
- TradingMetricsHealth schema in schemas/health.py

## Test count
- Baseline: 359; Phase 4: 376 (+17 new tests)
