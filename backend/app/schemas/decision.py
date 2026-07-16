"""schemas/decision.py — Pydantic response schemas for the Decision Engine.

Phase Next — Decision Engine Intelligence Upgrade:
  DecisionLogResponse gains consensus_score, agreement_level,
  conflict_detected, entry_quality_score (Phases 1 & 3).
  DecisionStatsResponse gains conflict_count, consensus_count,
  avg_entry_quality (Phase 8 Engine Health).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DecisionLogResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    decision: str
    confidence: float
    vote_score: float

    # Phase 1: Consensus Engine
    consensus_score: Optional[float] = None
    agreement_level: Optional[float] = None
    conflict_detected: Optional[bool] = None

    # Phase 3: Entry Quality Engine
    entry_quality_score: Optional[float] = None

    signal_confidence: Optional[float] = None
    signal_regime: Optional[str] = None

    momentum_score: Optional[float] = None
    momentum_direction: Optional[str] = None

    trend_score: Optional[float] = None
    trend_direction: Optional[str] = None

    volatility_score: Optional[float] = None
    volatility_regime: Optional[str] = None

    opportunity_score: Optional[float] = None
    opportunity_direction: Optional[str] = None

    risk_score: Optional[float] = None
    risk_gated: Optional[bool] = None

    market_quality_score: Optional[float] = None
    market_quality: Optional[str] = None
    market_confidence: Optional[float] = None
    market_risk: Optional[str] = None

    market_context_status: Optional[str] = None
    market_context_confidence: Optional[float] = None

    orderbook_direction: Optional[str] = None
    orderbook_confidence: Optional[float] = None

    funding_direction: Optional[str] = None
    funding_confidence: Optional[float] = None

    news_sentiment: Optional[str] = None
    news_confidence: Optional[float] = None

    supporting_engines: Optional[str] = None
    reasons: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionStatsResponse(BaseModel):
    """
    Phase 8 — Engine Health Statistics.

    Aggregates the most-recent decision per active market:
      - BUY_YES / BUY_NO / WAIT counts
      - conflict_count  — how many markets have engine disagreement
      - consensus_count — how many markets have strong engine agreement (≥70% weight aligned)
      - avg_confidence  — mean confidence across all markets
      - avg_entry_quality — mean entry quality score (Phase 3)
    """
    total_markets: int
    buy_yes_count: int
    buy_no_count: int
    wait_count: int
    conflict_count: int
    consensus_count: int
    avg_confidence: float
    avg_entry_quality: float
