"""
MomentumScore model — Decision Engine pipeline, stage 2 (Momentum).

One row per (asset, timeframe) pair — UPSERT on every cycle, mirroring the
Opportunity model's "one current row per key" pattern. Computed purely from
Binance klines (ROC, RSI, EMA fast/slow crossover); never touches market
(Polymarket) data.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MomentumScore(Base):
    __tablename__ = "momentum_scores"
    __table_args__ = (
        Index("ix_momentum_asset_tf", "asset", "timeframe", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 composite momentum strength score",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 — how much the sub-signals (ROC/RSI/EMA cross) agree",
    )
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BULLISH | BEARISH | NEUTRAL",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable explanation, sub-signals joined by ' | '",
    )

    roc_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_fast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_slow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MomentumScore {self.asset}/{self.timeframe} "
            f"score={self.score:.1f} direction={self.direction}>"
        )
