"""schemas/risk.py — Pydantic response schemas for Layer 9: Risk Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CapitalStatusDetailedResponse(BaseModel):
    """One-stop capital-status response for GET /api/v1/risk/capital-status.

    Single source of truth: frontend must use this endpoint only — do not
    reconstruct blocked state from multiple unrelated endpoints.
    """

    # ── Gate ──────────────────────────────────────────────────────────────────
    capital_blocked: bool
    block_code: Optional[str]        # machine code, e.g. "MAX_DRAWDOWN_LIMIT"
    block_reason: Optional[str]      # human label, e.g. "MAX DRAWDOWN LIMIT"
    block_scope: str                 # "DAILY" | "WEEKLY" | "SESSION" | "PERMANENT" | "NONE"
    blocked_at: Optional[str]        # ISO-8601 UTC; set when capital_blocked=True
    blocked_until: Optional[str]     # ISO-8601 UTC or None when rule-based auto-clear
    reset_policy: str
    reset_available: bool

    # ── Equity ────────────────────────────────────────────────────────────────
    initial_capital: float
    current_equity: float
    peak_equity: float
    drawdown_amount: float
    drawdown_percent: float
    max_drawdown_limit: float

    # ── Daily ─────────────────────────────────────────────────────────────────
    daily_start_equity: float
    daily_loss_amount: float
    daily_drawdown_percent: float
    daily_loss_limit: float

    # ── Consecutive losses ────────────────────────────────────────────────────
    consecutive_losses: int
    consecutive_loss_limit: int

    # ── Portfolio ─────────────────────────────────────────────────────────────
    open_exposure: float
    available_capital: float
    daily_pnl: float
    weekly_pnl: float

    # ── Meta ──────────────────────────────────────────────────────────────────
    data_source: str
    last_updated_at: str


class RiskEventResponse(BaseModel):
    id: int
    decision_id: int
    condition_id: str
    asset: str
    timeframe: str
    result: str
    reason: Optional[str]
    checked_at: datetime
    open_positions_count: int
    daily_loss: float
    daily_trades: int

    model_config = {"from_attributes": True}


class RiskStatsResponse(BaseModel):
    total_checked: int
    allowed: int
    blocked: int
    block_rate_pct: float
    by_reason: dict[str, int]
