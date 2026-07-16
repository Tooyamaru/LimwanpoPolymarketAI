"""
EngineWeight model — dynamic engine weights derived from historical performance.

One row per engine name (UPSERT).  Updated by DynamicWeightService every
DYNAMIC_WEIGHT_INTERVAL_SECONDS based on EnginePerformance statistics.

Priority 3: Dynamic Engine Weight
  - Engines that are right more often get higher weight.
  - Engines that are wrong more often get lower weight.
  - Min/max bounds prevent any single engine from dominating.
  - At least DYNAMIC_WEIGHT_MIN_OUTCOMES required before adjustment.

No Machine Learning. Pure statistics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Base weights (hardcoded defaults from decision_engine.py)
BASE_WEIGHTS: dict[str, float] = {
    "opportunity": 0.30,
    "orderbook":   0.20,
    "momentum":    0.10,
    "trend":       0.10,
    "funding":     0.10,
}

# Min/max bounds (no engine can be completely silenced or dominate)
WEIGHT_MIN: dict[str, float] = {
    "opportunity": 0.15,
    "orderbook":   0.08,
    "momentum":    0.04,
    "trend":       0.04,
    "funding":     0.04,
}
WEIGHT_MAX: dict[str, float] = {
    "opportunity": 0.50,
    "orderbook":   0.35,
    "momentum":    0.20,
    "trend":       0.20,
    "funding":     0.18,
}


class EngineWeight(Base):
    __tablename__ = "engine_weights"
    __table_args__ = (
        Index("ix_ew_engine_name", "engine_name", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    engine_name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        comment="opportunity | orderbook | momentum | trend | funding",
    )

    # Weights
    base_weight: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Original hardcoded weight (constant reference)",
    )
    current_weight: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Current effective weight (adjusted by performance)",
    )
    min_weight: Mapped[float] = mapped_column(Float, nullable=False)
    max_weight: Mapped[float] = mapped_column(Float, nullable=False)

    # Adjustment metadata
    adjustment_factor: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Last computed adjustment: (accuracy - 0.5) * 2 * 0.30",
    )
    outcomes_evaluated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="How many outcomes were used to compute this weight",
    )
    accuracy_at_adjustment: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Engine accuracy (0-100) that produced this weight",
    )

    # Priority 7: Smart dynamic engine weight — recency & stability
    recency_accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — exponentially decay-weighted accuracy over the most recent outcomes window",
    )
    stability_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — consistency of correctness over the recent window; higher = less volatile",
    )
    factor_breakdown: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON string of all component factors that produced current_weight (transparency/debug)",
    )

    last_adjusted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<EngineWeight {self.engine_name} "
            f"base={self.base_weight:.3f} current={self.current_weight:.3f} "
            f"accuracy={self.accuracy_at_adjustment}>"
        )
