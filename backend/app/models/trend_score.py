"""
TrendScore model — Decision Engine pipeline, stage 3 (Trend).

One row per (asset, timeframe) pair — UPSERT on every cycle. Computed from
Binance klines (MACD + EMA20/EMA50 slope); never touches market
(Polymarket) data.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrendScore(Base):
    __tablename__ = "trend_scores"
    __table_args__ = (
        Index("ix_trend_asset_tf", "asset", "timeframe", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 composite trend strength score",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 — how much MACD and EMA slope agree",
    )
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="UP | DOWN | SIDEWAYS",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable explanation, sub-signals joined by ' | '",
    )

    macd_line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_hist: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_fast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_slow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<TrendScore {self.asset}/{self.timeframe} "
            f"score={self.score:.1f} direction={self.direction}>"
        )
