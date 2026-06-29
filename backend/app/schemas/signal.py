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

    confidence_score: Optional[float]
    regime: Optional[str]
    mtf_confirmed: Optional[bool]

    snapshot_id_before: Optional[int]
    snapshot_id_after: Optional[int]

    detected_at: datetime

    model_config = {"from_attributes": True}


class RankedSignalResponse(BaseModel):
    """Signal with rank metadata — used by GET /signals/ranked."""

    id: int
    rank: int
    condition_id: str
    asset: str
    timeframe: str

    signal_type: str
    severity: str
    confidence_score: Optional[float]
    regime: Optional[str]
    mtf_confirmed: Optional[bool]

    yes_mid_after: Optional[float]
    yes_mid_delta: Optional[float]
    seed_deviation: Optional[float]
    spread_after: Optional[float]

    detected_at: datetime

    model_config = {"from_attributes": True}


class SignalStatsResponse(BaseModel):
    total_signals: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_regime: dict[str, int]
    avg_confidence: Optional[float]
    mtf_confirmed_count: int
