"""schemas/analytics.py — Pydantic response schemas for Layer 15: Performance Analytics."""

from typing import Optional

from pydantic import BaseModel


class BreakdownEntry(BaseModel):
    """Per-asset or per-timeframe trade statistics."""
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_profit: float


class PerformanceAnalyticsResponse(BaseModel):
    """Full trading performance report based on CLOSED positions only."""

    # ── Trade counts ──────────────────────────────────────────────────────────
    total_trades: int
    winning_trades: int
    losing_trades: int

    # ── Rate metrics ──────────────────────────────────────────────────────────
    win_rate: float

    # ── PnL components ────────────────────────────────────────────────────────
    gross_profit: float
    gross_loss: float
    net_profit: float

    # ── Per-trade averages ────────────────────────────────────────────────────
    average_win: float
    average_loss: float

    # ── Quality metrics ───────────────────────────────────────────────────────
    profit_factor: Optional[float]
    expectancy: float
    max_drawdown_usdc: float

    # ── Breakdowns ────────────────────────────────────────────────────────────
    assets: dict[str, BreakdownEntry]
    timeframes: dict[str, BreakdownEntry]
