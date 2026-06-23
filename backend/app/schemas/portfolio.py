"""schemas/portfolio.py — Pydantic response schemas for Layer 10: Portfolio Reporting."""

from pydantic import BaseModel


class PortfolioSummaryResponse(BaseModel):
    total_positions: int
    open_positions: int
    closed_positions: int
    total_orders: int
    executed_orders: int
    approved_decisions: int
    blocked_decisions: int


class PositionSummaryResponse(BaseModel):
    total_positions: int
    open_positions: int
    closed_positions: int
    by_asset: dict[str, int]
    by_side: dict[str, int]


class OrderSummaryResponse(BaseModel):
    total_orders: int
    filled_orders: int
    pending_orders: int
    by_asset: dict[str, int]
    by_side: dict[str, int]


class RiskSummaryResponse(BaseModel):
    total_checked: int
    allowed: int
    blocked: int
    block_rate_pct: float
    by_reason: dict[str, int]


class PnlSummaryResponse(BaseModel):
    open_positions: int
    total_unrealized_pnl: float
    average_unrealized_pnl: float
    closed_positions: int
    total_realized_pnl: float
