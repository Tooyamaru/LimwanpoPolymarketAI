"""
Market response schemas — Layer 1: Collector / Sprint 2.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    polymarket_market_id: str
    title: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str

    model_config = {"from_attributes": True}


class SnapshotResponse(BaseModel):
    id: int
    market_id: int
    timestamp: datetime
    yes_price: Optional[float]
    no_price: Optional[float]
    liquidity: Optional[float]
    volume: Optional[float]
    binance_price: Optional[float]

    model_config = {"from_attributes": True}
