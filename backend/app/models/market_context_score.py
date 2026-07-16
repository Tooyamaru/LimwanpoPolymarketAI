"""
MarketContextScore model — Market Context Engine (Phase Next).

An asset must be read as ONE structure, not as isolated timeframes. This
engine checks whether the asset's active timeframes (e.g. 5m/15m/1H) agree
on direction (per the supporting Momentum engine), and reports whether the
overall context is ALIGNED, MIXED, or in CONFLICT.

One row per asset — UPSERT on every cycle. Read-only with respect to
momentum_scores / market_universe.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketContextScore(Base):
    __tablename__ = "market_context_scores"
    __table_args__ = (
        Index("ix_market_context_asset", "asset", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="ALIGNED | MIXED | CONFLICT — do this asset's timeframes agree?",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 — strength of timeframe agreement",
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    timeframes_evaluated: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="Comma-joined list of timeframes considered, e.g. '5m,15m,1H'",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<MarketContextScore {self.asset} status={self.status}>"
