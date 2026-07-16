"""
MarketTypePerformance model — Priority 5: Market Type Performance.

One row per (asset, timeframe, market_type) combination, recomputed from
outcome_learnings every OutcomeLearningService cycle.  Tracks accuracy, win
rate, average pnl, max drawdown, and average confidence for each market
segment so the strategy layer can see which asset/timeframe/market_type
combos are actually profitable.

No Machine Learning. Pure statistics.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketTypePerformance(Base):
    __tablename__ = "market_type_performance"
    __table_args__ = (
        UniqueConstraint("asset", "timeframe", "market_type", name="uq_mtp_asset_tf_type"),
        Index("ix_mtp_asset_tf", "asset", "timeframe"),
        Index("ix_mtp_market_type", "market_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    market_type: Mapped[str] = mapped_column(String(32), nullable=False)

    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    win_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — fraction of trades with actual_pnl > 0",
    )
    accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — wins / (wins + losses) by AI prediction correctness",
    )
    avg_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Largest peak-to-trough cumulative pnl decline within this segment",
    )
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketTypePerformance {self.asset}/{self.timeframe}/{self.market_type} "
            f"accuracy={self.accuracy} trades={self.total_trades}>"
        )
