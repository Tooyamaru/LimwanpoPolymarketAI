"""schemas/market_context.py — Pydantic response schemas for the Market Context Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketContextResponse(BaseModel):
    id: int
    asset: str
    status: str
    confidence: float
    reason: Optional[str]
    timeframes_evaluated: Optional[str]
    computed_at: datetime

    model_config = {"from_attributes": True}
