"""schemas/news.py — Pydantic response schemas for the News Engine (stub/deferred)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NewsScoreResponse(BaseModel):
    id: int
    asset: str
    sentiment: str
    confidence: float
    reason: Optional[str]
    computed_at: datetime

    model_config = {"from_attributes": True}
