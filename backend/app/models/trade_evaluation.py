"""
TradeEvaluation model — Phase 5: Trade Evaluation.

One row per evaluated closed position.  Records a per-trade quality score that
grades the entry timing, exit timing, and overall P&L efficiency against the
theoretical maximum that was available in the market window.

Quality grades:
  A  — quality_score >= 80
  B  — quality_score >= 60
  C  — quality_score >= 40
  D  — quality_score >= 20
  F  — quality_score < 20

This table is append-only; re-evaluation overwrites via upsert on position_id.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TradeEvaluation(Base):
    __tablename__ = "trade_evaluations"
    __table_args__ = (
        Index("ix_te_position_id", "position_id", unique=True),
        Index("ix_te_grade", "grade"),
        Index("ix_te_quality_score", "quality_score"),
        Index("ix_te_evaluated_at", "evaluated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # FK to positions.id (not enforced at DB level for paper-mode simplicity)
    position_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True,
        comment="FK → positions.id",
    )

    # ── Component scores (0–100 each) ─────────────────────────────────────────
    entry_quality: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="How close the entry price was to the theoretical best price (0–100)",
    )
    exit_quality: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="How close the exit price was to the theoretical best exit (0–100)",
    )
    timing_score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Hold duration efficiency: not too short, not too long (0–100)",
    )
    pnl_efficiency: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Realized PnL as % of theoretical max PnL achievable in that trade (0–100)",
    )

    # ── Composite score and grade ──────────────────────────────────────────────
    quality_score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Weighted composite of the four component scores (0–100)",
    )
    grade: Mapped[str] = mapped_column(
        String(2), nullable=False,
        comment="A | B | C | D | F derived from quality_score",
    )

    # ── Context snapshots captured at evaluation time ─────────────────────────
    opportunity_score_at_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Opportunity engine score at the time of position open",
    )
    signal_confidence_at_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Signal confidence_score at the time of position open",
    )

    # ── PnL metadata ──────────────────────────────────────────────────────────
    realized_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Copy of positions.realized_pnl at evaluation time",
    )
    theoretical_max_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Max PnL achievable if exited at peak_pnl_usdc",
    )

    # ── Priority 4: Entry quality validation ──────────────────────────────────
    best_price_after_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Lowest effective price observed for this side between open and close",
    )
    worst_price_after_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Highest effective price observed for this side between open and close",
    )
    avg_price_after_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Mean effective price observed for this side between open and close",
    )
    entry_efficiency: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — how close entry_price was to best_price_after_entry vs worst_price_after_entry",
    )
    entry_timing_label: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True,
        comment="OPTIMAL | EARLY | LATE | POOR | UNKNOWN",
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    close_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hold_minutes: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="How long the position was open in minutes",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<TradeEvaluation id={self.id} position_id={self.position_id} "
            f"grade={self.grade} score={self.quality_score:.1f}>"
        )
