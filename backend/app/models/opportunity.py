"""
Opportunity model — Layer 5: Opportunity Engine.

One row per active market. UPSERTED on every engine scan cycle so each row
always reflects the most current opportunity assessment.

Opportunity Score (0–100) is composed of five weighted sub-scores:

  score_mid_movement    (0–30)  Distance of yes_mid from seed price 0.50
  score_spread          (0–20)  Spread tightness — tighter = more tradeable
  score_depth_imbalance (0–20)  Bid/ask imbalance between YES and NO sides
  score_signal_activity (0–20)  Recent MID_MOVE / SEED_DEVIATION signal count
  score_discovery       (0–10)  Time proximity to market expiry

Direction hint (based on mean-reversion against seed 0.50):
  BUY_YES  — yes_mid < 0.495 (market under-priced)
  BUY_NO   — yes_mid > 0.505 (market over-priced)
  NEUTRAL  — within ±0.5 % of seed
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("condition_id", name="uq_opportunity_condition_id"),
        Index("ix_opportunity_score", "opportunity_score"),
        Index("ix_opportunity_asset_tf", "asset", "timeframe"),
        Index("ix_opportunity_direction", "direction"),
        Index("ix_opportunity_evaluated_at", "evaluated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    # ── Overall score ─────────────────────────────────────────────────────────
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Score components ──────────────────────────────────────────────────────
    score_mid_movement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_spread: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_depth_imbalance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_signal_activity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_discovery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Raw market inputs ─────────────────────────────────────────────────────
    yes_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_yes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_no: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clob_fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when CLOB snapshot was fetched for this opportunity row",
    )

    seed_deviation: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="abs(yes_mid - 0.50)",
    )

    # ── Signal context ────────────────────────────────────────────────────────
    signal_count_1h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_signal_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_signal_severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # ── Discovery context ─────────────────────────────────────────────────────
    minutes_to_expiry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Minutes until market end_time; NULL if no end_time known",
    )

    # ── Trade direction hint ──────────────────────────────────────────────────
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, default="NEUTRAL",
        comment="BUY_YES | BUY_NO | NEUTRAL based on mean-reversion vs seed 0.50",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Opportunity id={self.id} {self.asset}/{self.timeframe} "
            f"score={self.opportunity_score:.1f} dir={self.direction}>"
        )
