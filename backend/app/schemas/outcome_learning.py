"""Schemas — Outcome Learning (Priority 1 + Priority 5 Feedback Loop)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OutcomeLearningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    condition_id: str
    asset: str
    timeframe: str
    prediction: str
    outcome_type: str
    correct: Optional[bool]
    actual_pnl: Optional[float]
    decision_log_id: Optional[int]
    confidence: Optional[float]
    consensus_score: Optional[float]
    agreement_level: Optional[float]
    conflict_detected: Optional[bool]
    entry_quality_score: Optional[float]
    market_quality: Optional[str]
    market_quality_score: Optional[float]
    vote_score: Optional[float]
    opportunity_direction: Optional[str]
    orderbook_direction: Optional[str]
    momentum_direction: Optional[str]
    trend_direction: Optional[str]
    funding_direction: Optional[str]
    confidence_calibration: Optional[str]
    entry_quality_evaluation: Optional[str]
    consensus_evaluation: Optional[str]
    feedback_summary: Optional[str]
    position_id: Optional[int]
    evaluated_at: datetime


class OutcomeLearningStatsResponse(BaseModel):
    total_evaluated: int
    with_position: int
    correct: int
    wrong: int
    unknown: int
    accuracy: float
    avg_confidence_when_correct: float
    avg_confidence_when_wrong: float
    overconfident_count: int
    underconfident_count: int
