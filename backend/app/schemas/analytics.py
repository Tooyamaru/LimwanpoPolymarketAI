"""schemas/analytics.py — Pydantic response schemas for Layers 15 & 16 Analytics.

Phase 2 vocabulary migration: serialization aliases expose new terminology in JSON
responses while internal Python field names remain unchanged.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BreakdownEntry(BaseModel):
    """Per-asset or per-timeframe prediction statistics."""

    model_config = ConfigDict(populate_by_name=True)

    trades: int = Field(serialization_alias="predictions")
    wins: int
    losses: int
    win_rate: float
    net_profit: float


class PerformanceAnalyticsResponse(BaseModel):
    """Full prediction performance report based on RESOLVED predictions only."""

    model_config = ConfigDict(populate_by_name=True)

    # ── Prediction counts ─────────────────────────────────────────────────────
    total_trades: int = Field(serialization_alias="total_predictions")
    winning_trades: int = Field(serialization_alias="winning_predictions")
    losing_trades: int = Field(serialization_alias="losing_predictions")

    # ── Rate metrics ──────────────────────────────────────────────────────────
    win_rate: float

    # ── Outcome components ────────────────────────────────────────────────────
    gross_profit: float
    gross_loss: float
    net_profit: float

    # ── Per-prediction averages ───────────────────────────────────────────────
    average_win: float
    average_loss: float

    # ── Quality metrics ───────────────────────────────────────────────────────
    profit_factor: Optional[float]
    expectancy: float
    max_drawdown_usdc: float

    # ── Holding time ──────────────────────────────────────────────────────────
    avg_hold_time_minutes: float
    longest_hold_time_minutes: float
    shortest_hold_time_minutes: float

    # ── Phase 4 Part C: split hold times ─────────────────────────────────────
    avg_winner_duration_minutes: float
    avg_loser_duration_minutes: float

    # ── Prediction excursion (realized proxies) ───────────────────────────────
    # MAE: worst single realized_pnl across all predictions (most negative value).
    # MFE: best single realized_pnl across all predictions (most positive value).
    mae_usdc: float
    mfe_usdc: float

    # ── Conversion ────────────────────────────────────────────────────────────
    # Percentage of OPEN_LONG decisions that reached EXECUTED status.
    opportunity_conversion_rate: float

    # ── Phase 4 Part C: signal quality & cost metrics ────────────────────────
    signal_precision: float
    avg_fee_usdc: float
    avg_slippage_usdc: float
    avg_time_to_stop_minutes: float
    avg_time_to_profit_minutes: float

    # ── Breakdowns ────────────────────────────────────────────────────────────
    assets: dict[str, BreakdownEntry]
    timeframes: dict[str, BreakdownEntry]


class CapitalStatusResponse(BaseModel):
    """Layer 16: Budget management kill-switch status."""

    model_config = ConfigDict(populate_by_name=True)

    # ── Gate ──────────────────────────────────────────────────────────────────
    allowed: bool
    reason: Optional[str]

    # ── Outcome metrics ───────────────────────────────────────────────────────
    daily_pnl: float = Field(serialization_alias="daily_outcome")
    weekly_pnl: float = Field(serialization_alias="weekly_outcome")
    consecutive_losses: int
    drawdown_percent: float
