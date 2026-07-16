"""schemas/orderbook.py — Pydantic response schemas for the Orderbook Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrderbookScoreResponse(BaseModel):
    id: int
    asset: str
    direction: str
    confidence: float
    reason: Optional[str]
    bid_volume: Optional[float]
    ask_volume: Optional[float]
    imbalance_pct: Optional[float]
    computed_at: datetime

    model_config = {"from_attributes": True}
