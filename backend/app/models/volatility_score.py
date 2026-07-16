"""
VolatilityScore model — Decision Engine pipeline, stage 4 (Volatility).

One row per (asset, timeframe) pair — UPSERT on every cycle. Computed from
Binance klines (ATR as a percentage of price); never touches market
(Polymarket) data.

The "score" here means tradability, not raw volatility: it peaks in the
MEDIUM regime (enough movement for the market to resolve directionally
within the window) and is penalised at both LOW (no movement, market will
likely settle flat) and HIGH (too erratic to trust the other engines'
directional read).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VolatilityScore(Base):
    __tablename__ = "volatility_scores"
    __table_args__ = (
        Index("ix_volatility_asset_tf", "asset", "timeframe", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 tradability score — peaks at MEDIUM volatility regime",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 — how clearly the ATR% falls inside a regime band",
    )
    regime: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="LOW | MEDIUM | HIGH",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable explanation",
    )

    atr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="ATR as a percentage of the last close",
    )
    last_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<VolatilityScore {self.asset}/{self.timeframe} "
            f"score={self.score:.1f} regime={self.regime}>"
        )
