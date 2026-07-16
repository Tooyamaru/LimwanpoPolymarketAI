"""schemas/trend.py — Pydantic response schemas for the Trend Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TrendScoreResponse(BaseModel):
    id: int
    asset: str
    timeframe: str

    score: float
    confidence: float
    direction: str
    reason: Optional[str]

    macd_line: Optional[float]
    macd_signal: Optional[float]
    macd_hist: Optional[float]
    ema_fast: Optional[float]
    ema_slow: Optional[float]

    computed_at: datetime

    model_config = {"from_attributes": True}
