"""schemas/risk.py — Pydantic response schemas for Layer 9: Risk Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RiskEventResponse(BaseModel):
    id: int
    decision_id: int
    condition_id: str
    asset: str
    timeframe: str
    result: str
    reason: Optional[str]
    checked_at: datetime
    open_positions_count: int
    daily_loss: float
    daily_trades: int

    model_config = {"from_attributes": True}


class RiskStatsResponse(BaseModel):
    total_checked: int
    allowed: int
    blocked: int
    block_rate_pct: float
    by_reason: dict[str, int]
