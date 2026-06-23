"""
Price snapshot response schemas — Layer 3b: Price Refresh / Sprint 9.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PriceSnapshotResponse(BaseModel):
    id: int
    condition_id: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]

    yes_bid: Optional[float]
    yes_ask: Optional[float]
    yes_mid: Optional[float]

    no_bid: Optional[float]
    no_ask: Optional[float]
    no_mid: Optional[float]

    spread_yes: Optional[float]
    spread_no: Optional[float]

    volume: Optional[float]
    liquidity: Optional[float]

    captured_at: datetime

    asset: Optional[str] = None
    timeframe: Optional[str] = None

    model_config = {"from_attributes": True}


class PriceStatsResponse(BaseModel):
    total_snapshots: int
    active_markets_with_data: int
    assets_covered: list[str]
    timeframes_covered: list[str]
