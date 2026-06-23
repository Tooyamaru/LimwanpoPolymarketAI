"""schemas/opportunity.py — Pydantic response schemas for Layer 5: Opportunity Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OpportunityResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    opportunity_score: float

    score_mid_movement: float
    score_spread: float
    score_depth_imbalance: float
    score_signal_activity: float
    score_discovery: float

    yes_mid: Optional[float]
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    no_mid: Optional[float]
    spread_yes: Optional[float]
    spread_no: Optional[float]
    seed_deviation: Optional[float]

    signal_count_1h: int
    last_signal_type: Optional[str]
    last_signal_severity: Optional[str]

    minutes_to_expiry: Optional[float]
    direction: str
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class OpportunityStatsResponse(BaseModel):
    total_markets: int
    markets_with_direction: int
    avg_score: float
    top_score: float
    top_asset: str | None
    top_timeframe: str | None
    buy_yes_count: int
    buy_no_count: int
    neutral_count: int
