"""schemas/position.py — Pydantic response schemas for Layer 8: Position Tracking."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PositionResponse(BaseModel):
    id: int
    order_id: int
    condition_id: str
    asset: str
    timeframe: str
    side: str
    quantity: float
    entry_price: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    realized_pnl: Optional[float]
    status: str
    opened_at: datetime
    closed_at: Optional[datetime]
    # Layer 12: exit audit trail
    close_reason: Optional[str] = None
    exit_price: Optional[float] = None
    close_decision_id: Optional[int] = None
    close_order_id: Optional[int] = None

    model_config = {"from_attributes": True}


class PositionStatsResponse(BaseModel):
    total_positions: int
    open: int
    closed: int
    total_unrealized_pnl: float
    total_realized_pnl: float
    avg_unrealized_pnl: float
