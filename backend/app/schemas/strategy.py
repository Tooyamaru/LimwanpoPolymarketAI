"""schemas/strategy.py — Pydantic response schemas for Layer 6: Strategy Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TradeDecisionResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    decision: str
    status: str

    opportunity_score: float
    direction: str

    yes_mid: Optional[float]
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    spread_yes: Optional[float]

    skip_reason: Optional[str]
    decided_at: datetime

    model_config = {"from_attributes": True}


class StrategyStatsResponse(BaseModel):
    total_decisions: int
    open_long_yes: int
    open_long_no: int
    watch: int
    skip: int
    avg_score_actionable: float
