"""schemas/market_quality.py — Pydantic response schemas for the Polymarket Market Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketQualityResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    market_score: float
    market_quality: str
    market_confidence: float
    market_risk: str
    reason: Optional[str]
    market_behaviours: Optional[str] = None

    yes_bid: Optional[float]
    yes_ask: Optional[float]
    spread_yes: Optional[float]
    liquidity: Optional[float]
    volume: Optional[float]
    seconds_to_expiry: Optional[float]
    active: Optional[bool]

    computed_at: datetime

    model_config = {"from_attributes": True}
