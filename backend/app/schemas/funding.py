"""schemas/funding.py — Pydantic response schemas for the Funding Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FundingScoreResponse(BaseModel):
    id: int
    asset: str
    direction: str
    confidence: float
    reason: Optional[str]
    funding_rate: Optional[float]
    open_interest: Optional[float]
    long_short_ratio: Optional[float]
    computed_at: datetime

    model_config = {"from_attributes": True}
