"""
Discovery response schemas — Layer 2: Scanner / Sprint 3.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DiscoveryDiagnosticsResponse(BaseModel):
    run_at: Optional[datetime]
    total_markets_scanned: int
    matched_markets: int
    btc: int
    eth: int
    sol: int
    xrp: int


class DiscoveryMarketResponse(BaseModel):
    market_id: str
    asset: str
    timeframe: str
    raw_title: str
    matching_rule: str
    detected_asset: str
    detected_timeframe: str
    health_status: str

    model_config = {"from_attributes": True}
