"""
EnginePerformance model — per-engine accuracy statistics.

One row per engine name (UPSERT).  Updated each time an outcome is learned
from OutcomeLearningService.

Priority 2: Engine Performance Tracking
  - Which engines are right most often?
  - Which engines contribute most to winning decisions?
  - Which engines should have higher/lower weight?

No Machine Learning. Pure statistics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnginePerformance(Base):
    __tablename__ = "engine_performance_stats"
    __table_args__ = (
        Index("ix_ep_engine_name", "engine_name", unique=True),
        Index("ix_ep_accuracy", "accuracy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    engine_name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        comment="opportunity | orderbook | momentum | trend | funding | market_context | market_quality | signal | risk",
    )

    # Outcome counters
    wins: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Times this engine's direction matched the correct outcome",
    )
    losses: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Times this engine's direction was opposite to the correct outcome",
    )
    abstentions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Times this engine had no data / neutral direction",
    )
    total_evaluated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Total outcomes where this engine had a directional opinion",
    )

    # Accuracy (wins / total_evaluated, 0-100)
    accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — fraction of directional predictions that were correct",
    )

    # Confidence calibration (do high-confidence predictions win more often?)
    avg_confidence_when_correct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_confidence_when_wrong: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Contribution score (accuracy weighted by participation rate)
    contribution_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — accuracy × participation_rate; high = accurate AND active",
    )
    contribution_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — this engine's share of total contribution_score across all engines",
    )

    # Grade
    grade: Mapped[Optional[str]] = mapped_column(
        String(2), nullable=True,
        comment="A | B | C | D | F derived from accuracy",
    )

    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<EnginePerformance {self.engine_name} "
            f"accuracy={self.accuracy} wins={self.wins} losses={self.losses} "
            f"grade={self.grade}>"
        )
