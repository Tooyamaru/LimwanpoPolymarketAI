"""
Universe response schemas — Layer 3: Universe Sync / Sprint 7.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UniverseMarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    series_slug: str
    series_id: Optional[str]
    event_id: Optional[str]
    condition_id: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]
    question: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimeframeStats(BaseModel):
    active: int
    upcoming: int
    expired: int


class AssetStats(BaseModel):
    total: int
    by_timeframe: dict[str, TimeframeStats]


class UniverseStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_asset: dict[str, AssetStats]
    by_timeframe: dict[str, dict[str, int]]


class SyncResponse(BaseModel):
    synced_at: str
    duration_ms: float
    series_processed: int
    markets_upserted: int
    markets_expired_by_time: int
    errors: list[str]
