"""Schemas — Engine Performance (Priority 2)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EnginePerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    engine_name: str
    wins: int
    losses: int
    abstentions: int
    total_evaluated: int
    accuracy: Optional[float]
    avg_confidence_when_correct: Optional[float]
    avg_confidence_when_wrong: Optional[float]
    contribution_score: Optional[float]
    grade: Optional[str]
    last_updated_at: datetime


class EnginePerformanceSummaryResponse(BaseModel):
    total_engines_tracked: int
    avg_accuracy: Optional[float]
    best_engine: Optional[str]
    worst_engine: Optional[str]
    engines: list[EnginePerformanceResponse]
