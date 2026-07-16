"""
FundingScore model — Funding Engine (Phase Next, supporting engine).

Reads Binance perpetual futures funding rate, open interest, and long/short
account ratio as a sentiment confirmation signal. Used only to HELP confirm
a decision derived from Polymarket data. One row per asset — UPSERT on every
cycle.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FundingScore(Base):
    __tablename__ = "funding_scores"
    __table_args__ = (
        Index("ix_funding_asset", "asset", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)

    direction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BULLISH | NEUTRAL | BEARISH — funding rate / OI / long-short ratio reading",
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_interest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    long_short_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<FundingScore {self.asset} direction={self.direction}>"
