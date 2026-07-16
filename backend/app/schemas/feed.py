"""schemas/feed.py — Pydantic response schemas for the AI Activity feed (Phase 5)."""

from datetime import datetime

from pydantic import BaseModel


class FeedEventResponse(BaseModel):
    tag: str
    message: str
    timestamp: datetime
