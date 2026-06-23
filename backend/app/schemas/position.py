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

    model_config = {"from_attributes": True}


class PositionStatsResponse(BaseModel):
    total_positions: int
    open: int
    closed: int
    total_unrealized_pnl: float
    total_realized_pnl: float
    avg_unrealized_pnl: float
