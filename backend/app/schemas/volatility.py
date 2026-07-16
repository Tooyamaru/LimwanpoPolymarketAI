"""schemas/volatility.py — Pydantic response schemas for the Volatility Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VolatilityScoreResponse(BaseModel):
    id: int
    asset: str
    timeframe: str

    score: float
    confidence: float
    regime: str
    reason: Optional[str]

    atr: Optional[float]
    atr_pct: Optional[float]
    last_close: Optional[float]

    computed_at: datetime

    model_config = {"from_attributes": True}
