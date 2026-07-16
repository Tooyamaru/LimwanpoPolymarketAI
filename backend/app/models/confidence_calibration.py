"""
Confidence calibration models — Priority 3 & 6: Confidence Calibration +
Confidence-vs-Performance Buckets.

ConfidenceBucketStat — one row per 5%-wide confidence bucket (50-55, 55-60, ...
95-100), recomputed from outcome_learnings every OutcomeLearningService cycle.

CalibrationSummary — single-row (id=1) rollup of Average Calibration Error
(ACE), Expected Calibration Error (ECE), and over/under/well-calibrated
percentages across all evaluated outcomes.

No Machine Learning. Pure statistics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfidenceBucketStat(Base):
    __tablename__ = "confidence_bucket_stats"
    __table_args__ = (
        Index("ix_cbs_bucket_min", "bucket_min", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bucket_min: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Lower bound of confidence bucket, e.g. 50.0, 55.0 ... 95.0 (or 0.0 for below-50 catch-all)",
    )
    bucket_max: Mapped[float] = mapped_column(Float, nullable=False)

    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — correct_count / sample_count",
    )
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_error: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="abs(accuracy - avg_confidence)",
    )
    avg_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — fraction of bucket trades with actual_pnl > 0",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<ConfidenceBucketStat {self.bucket_min}-{self.bucket_max} "
            f"n={self.sample_count} accuracy={self.accuracy}>"
        )


class CalibrationSummary(Base):
    __tablename__ = "calibration_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ace: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Average Calibration Error — unweighted mean of per-bucket |accuracy - avg_confidence|",
    )
    ece: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Expected Calibration Error — sample-weighted mean of per-bucket |accuracy - avg_confidence|",
    )
    overconfident_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    underconfident_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    well_calibrated_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<CalibrationSummary ace={self.ace} ece={self.ece} n={self.total_evaluated}>"
