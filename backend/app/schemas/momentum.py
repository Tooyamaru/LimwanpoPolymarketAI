"""schemas/momentum.py — Pydantic response schemas for the Momentum Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MomentumScoreResponse(BaseModel):
    id: int
    asset: str
    timeframe: str

    score: float
    confidence: float
    direction: str
    reason: Optional[str]

    roc_pct: Optional[float]
    rsi: Optional[float]
    ema_fast: Optional[float]
    ema_slow: Optional[float]
    last_close: Optional[float]

    computed_at: datetime

    model_config = {"from_attributes": True}
