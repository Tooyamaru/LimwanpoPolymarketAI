"""schemas/evaluation.py — Pydantic response schemas for Phase 5 Trade Evaluation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Individual trade evaluation ───────────────────────────────────────────────

class TradeEvaluationSchema(BaseModel):
    """Per-trade quality evaluation result."""
    id: int
    position_id: int
    asset: str
    timeframe: str
    close_reason: Optional[str]
    hold_minutes: Optional[float]

    entry_quality: float
    exit_quality: float
    timing_score: float
    pnl_efficiency: float
    quality_score: float
    grade: str

    opportunity_score_at_entry: Optional[float]
    signal_confidence_at_entry: Optional[float]
    realized_pnl: Optional[float]
    theoretical_max_pnl: Optional[float]
    evaluated_at: datetime

    model_config = {"from_attributes": True}


# ── Evaluation summary ────────────────────────────────────────────────────────

class GradeDistribution(BaseModel):
    """Count of evaluations per grade."""
    A: int = 0
    B: int = 0
    C: int = 0
    D: int = 0
    F: int = 0


class EvaluationSummaryResponse(BaseModel):
    """Aggregate trade evaluation statistics."""
    total_evaluated: int
    avg_quality_score: float
    avg_entry_quality: float
    avg_exit_quality: float
    avg_timing_score: float
    avg_pnl_efficiency: float
    grade_distribution: GradeDistribution
    best_grade_asset: Optional[str]
    worst_grade_asset: Optional[str]


# ── Engine scorecard ──────────────────────────────────────────────────────────

class EngineScoreEntry(BaseModel):
    """Per-engine performance score."""
    score: float               # 0–100
    label: str                 # human-readable description
    numerator: int
    denominator: int


class EngineScorecardResponse(BaseModel):
    """
    Engine performance scorecard.

    Each engine layer is scored on how accurately its output led to
    positive downstream outcomes.
    """
    # Signal → Opportunity conversion
    signal_accuracy: EngineScoreEntry

    # Opportunity → Strategy (OPEN_LONG decision) conversion
    opportunity_accuracy: EngineScoreEntry

    # Strategy (OPEN_LONG) → Execution conversion
    strategy_execution_rate: EngineScoreEntry

    # Executed positions → profitable closes
    execution_win_rate: EngineScoreEntry

    # Risk blocks that would have been losses (protective effectiveness)
    risk_effectiveness: EngineScoreEntry

    # Composite weighted score across all engines
    composite_score: float
    composite_grade: str


# ── Trade replay ─────────────────────────────────────────────────────────────

class ReplayEvent(BaseModel):
    """One step in a trade replay timeline."""
    step: int
    event: str
    timestamp: Optional[datetime]
    value: Optional[float]
    note: str


class TradeReplayResponse(BaseModel):
    """Full replay of a single closed trade."""
    position_id: int
    asset: str
    timeframe: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    realized_pnl: Optional[float]
    close_reason: Optional[str]
    hold_minutes: Optional[float]
    evaluation: Optional[TradeEvaluationSchema]
    timeline: list[ReplayEvent]


# ── Dataset export ────────────────────────────────────────────────────────────

class TradeDatasetRow(BaseModel):
    """Flat row suitable for ML / statistical analysis."""
    position_id: int
    asset: str
    timeframe: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    realized_pnl: Optional[float]
    total_fee_usdc: Optional[float]
    close_reason: Optional[str]
    hold_minutes: Optional[float]
    opportunity_score_at_entry: Optional[float]
    signal_confidence_at_entry: Optional[float]
    quality_score: Optional[float]
    grade: Optional[str]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]


class TradeDatasetResponse(BaseModel):
    """Full dataset of all closed trades for export / analysis."""
    total_rows: int
    rows: list[TradeDatasetRow]


# ── Trades listing ────────────────────────────────────────────────────────────

class TradeSummaryRow(BaseModel):
    """Single closed trade with evaluation data for the list endpoint."""
    position_id: int
    asset: str
    timeframe: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    realized_pnl: Optional[float]
    total_fee_usdc: Optional[float]
    close_reason: Optional[str]
    hold_minutes: Optional[float]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    quality_score: Optional[float]
    grade: Optional[str]


class TradesListResponse(BaseModel):
    """Paginated list of closed trades."""
    total: int
    limit: int
    offset: int
    trades: list[TradeSummaryRow]
