"""
OutcomeLearning model — AI feedback loop.

Append-only evaluation of every closed Polymarket market where the AI made
a prediction.  One row per condition_id (upserted).

This is the foundation for:
  Priority 1 — Outcome Learning (was the AI right?)
  Priority 2 — Engine Performance Tracking (which engines were right?)
  Priority 5 — Paper Trading Feedback Loop (was confidence calibrated?)

No Machine Learning. Pure statistics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OutcomeLearning(Base):
    __tablename__ = "outcome_learnings"
    __table_args__ = (
        Index("ix_ol_condition_id", "condition_id", unique=True),
        Index("ix_ol_asset_tf", "asset", "timeframe"),
        Index("ix_ol_correct", "correct"),
        Index("ix_ol_evaluated_at", "evaluated_at"),
        Index("ix_ol_prediction", "prediction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Market identification
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    # AI prediction (from decision_logs — latest before market expiry)
    prediction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BUY_YES | BUY_NO | WAIT — last AI decision before market closed",
    )

    # Actual outcome
    outcome_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="POSITION (traded) | NO_POSITION (predicted but not traded) | WAIT_CORRECT | WAIT_UNKNOWN",
    )
    correct: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True,
        comment="True=AI was right, False=AI was wrong, None=cannot determine",
    )
    actual_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Position realized_pnl if a trade was taken, else None",
    )

    # AI snapshot at decision time (from decision_logs)
    decision_log_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consensus_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    agreement_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conflict_detected: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    entry_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_quality: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    market_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vote_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Per-engine directions at decision time (for engine performance tracking)
    opportunity_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    orderbook_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    momentum_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    trend_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    funding_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Priority 5: Feedback loop quality metrics
    # Was confidence correctly calibrated?
    confidence_calibration: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="WELL_CALIBRATED | OVERCONFIDENT | UNDERCONFIDENT | UNKNOWN",
    )
    # Was entry quality meaningful?
    entry_quality_evaluation: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="GOOD_FILTER | MISSED | FALSE_POSITIVE | UNKNOWN",
    )
    # Was consensus useful?
    consensus_evaluation: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="RELIABLE | CONFLICTED_AND_WRONG | CONFLICTED_AND_LUCKY | UNKNOWN",
    )

    # Human-readable feedback summary
    feedback_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Position reference (if traded)
    position_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Priority 1: Market-level learning
    market_title: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True,
        comment="Human-readable market question/title at evaluation time",
    )
    market_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True,
        comment="UP_DOWN | OTHER — derived from Gamma series_slug",
    )
    entry_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Position.opened_at if a trade was taken",
    )
    close_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Position.closed_at, else market end_time",
    )
    ai_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 composite: confidence*0.5 + consensus_score*0.3 + entry_quality_score*0.2",
    )

    # Phase 9D: Direct Polymarket resolution fields
    # outcome_source: how correctness was determined
    #   DIRECT_POLYMARKET_RESOLUTION — winner proven from Gamma API outcomePrices
    #   REALIZED_PNL_PROXY           — fallback: position PnL > 0
    #   NOT_AVAILABLE                — no position and no direct resolution
    outcome_source: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="DIRECT_POLYMARKET_RESOLUTION | REALIZED_PNL_PROXY | NOT_AVAILABLE",
    )
    # winning_side: only set when outcome_source == DIRECT_POLYMARKET_RESOLUTION
    winning_side: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True,
        comment="YES | NO — only populated when outcome_source = DIRECT_POLYMARKET_RESOLUTION",
    )
    winning_token_id: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True,
        comment="CLOB token ID of the winning outcome token",
    )
    final_yes_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Gamma outcomePrices[0] at resolution time",
    )
    final_no_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Gamma outcomePrices[1] at resolution time",
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable resolution classification reason from Gamma lookup",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<OutcomeLearning {self.asset}/{self.timeframe} "
            f"pred={self.prediction} correct={self.correct} "
            f"source={self.outcome_source} conf={self.confidence}>"
        )
