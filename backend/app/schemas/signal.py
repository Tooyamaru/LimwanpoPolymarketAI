"""schemas/signal.py — Pydantic response schemas for Layer 4: Signal Engine."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SignalResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    signal_type: str
    severity: str

    yes_mid_before: Optional[float]
    yes_mid_after: Optional[float]
    yes_mid_delta: Optional[float]

    spread_before: Optional[float]
    spread_after: Optional[float]
    spread_delta: Optional[float]

    seed_deviation: Optional[float]

    snapshot_id_before: Optional[int]
    snapshot_id_after: Optional[int]

    detected_at: datetime

    model_config = {"from_attributes": True}


class SignalStatsResponse(BaseModel):
    total_signals: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
