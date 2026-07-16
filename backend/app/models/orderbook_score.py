"""
OrderbookScore model — Orderbook Engine (Phase Next, supporting engine).

Reads Binance spot order book depth to gauge short-term bid/ask pressure.
Used only to HELP confirm a decision derived from Polymarket data — never to
replace it. One row per asset — UPSERT on every cycle.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderbookScore(Base):
    __tablename__ = "orderbook_scores"
    __table_args__ = (
        Index("ix_orderbook_asset", "asset", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)

    direction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BULLISH | NEUTRAL | BEARISH — bid/ask volume imbalance reading",
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    bid_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imbalance_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<OrderbookScore {self.asset} direction={self.direction}>"
