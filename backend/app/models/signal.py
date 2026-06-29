"""
Signal model — Layer 4: Signal Engine.

One row per detected price event. The signal engine compares consecutive
market_price_snapshots and emits a signal whenever a meaningful change
is detected.

Signal types (based on Audit #1-#5 findings):
  MID_MOVE       — yes_mid changed from the previous snapshot
  SEED_DEVIATION — abs(yes_mid - 0.50) >= 0.01 (market moved from seed)
  SPREAD_CHANGE  — spread changed by >= 0.005

Severity:
  LOW    — small change, informational
  MEDIUM — notable change, worth watching
  HIGH   — large move, potential trade opportunity

Phase 1 AI additions:
  confidence_score — 0–100 composite quality score (see signal_confidence.py)
  regime           — RANGING | TRENDING_UP | TRENDING_DOWN | VOLATILE | UNKNOWN
  mtf_confirmed    — True when ≥ 2 timeframes for the same asset fired in the
                     same scan cycle (multi-timeframe confirmation)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_condition_detected", "condition_id", "detected_at"),
        Index("ix_signals_asset_tf", "asset", "timeframe"),
        Index("ix_signals_type_severity", "signal_type", "severity"),
        Index("ix_signals_confidence", "confidence_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    signal_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    yes_mid_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_mid_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_mid_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    spread_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    seed_deviation: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="abs(yes_mid_after - 0.50), populated for SEED_DEVIATION signals",
    )

    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="LOW", index=True
    )

    # ── Phase 1 AI Signal Engine additions ───────────────────────────────────
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0–100 composite quality score computed by signal_confidence.py",
    )
    regime: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True,
        comment="Market micro-regime at signal time: RANGING|TRENDING_UP|TRENDING_DOWN|VOLATILE|UNKNOWN",
    )
    mtf_confirmed: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False,
        comment="True when ≥2 timeframes for the same asset fired in this scan cycle",
    )

    snapshot_id_before: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("market_price_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot_id_after: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("market_price_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal id={self.id} type={self.signal_type} "
            f"asset={self.asset}/{self.timeframe} "
            f"delta={self.yes_mid_delta} severity={self.severity} "
            f"confidence={self.confidence_score}>"
        )
