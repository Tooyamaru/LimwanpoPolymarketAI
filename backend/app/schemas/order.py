"""schemas/order.py — Pydantic response schemas for Layer 7: Execution Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrderResponse(BaseModel):
    id: int
    decision_id: int
    condition_id: str
    asset: str
    timeframe: str
    side: str
    order_type: str
    quantity: float
    requested_price: Optional[float]
    filled_price: Optional[float]
    status: str
    created_at: datetime
    filled_at: Optional[datetime]

    model_config = {"from_attributes": True}


class OrderStatsResponse(BaseModel):
    total_orders: int
    filled: int
    pending: int
    cancelled: int
    failed: int
    long_yes_filled: int
    long_no_filled: int
    avg_fill_price_yes: float
    avg_fill_price_no: float
