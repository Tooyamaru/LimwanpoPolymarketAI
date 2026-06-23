"""
Classifier response schemas — Layer 2: Event Classifier / Sprint 4.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClassificationResponse(BaseModel):
    id: int
    market_id: str
    raw_title: str
    event_type: str
    confidence: float
    matched_rule: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassifierStatsResponse(BaseModel):
    """
    Aggregate classification statistics.

    total = total markets scanned in the latest discovery run.
    All event-type counts come from that run's in-memory classification pass,
    so they represent ALL scanned markets (not just the asset+timeframe subset).
    """

    total: int
    updown: int
    price_range: int
    news_event: int
    politics: int
    other: int
    run_at: Optional[datetime] = None
