"""
Scanner response schemas — Layer 2: Market Scanner / Sprint 3.
"""

from datetime import datetime

from pydantic import BaseModel


class ScannerMarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    market_id: str
    health_status: str
    created_at: datetime
    raw_title: str
    matching_rule: str
    detected_asset: str
    detected_timeframe: str

    model_config = {"from_attributes": True}


class AssetBreakdown(BaseModel):
    BTC: int
    ETH: int
    SOL: int
    XRP: int


class ScannerStatsResponse(BaseModel):
    total: int
    active: int
    stale: int
    by_asset: AssetBreakdown
