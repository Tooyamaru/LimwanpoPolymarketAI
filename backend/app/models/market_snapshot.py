from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_snapshots_market_timestamp", "market_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(
        ForeignKey("markets.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    yes_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    binance_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    market: Mapped["Market"] = relationship("Market", back_populates="snapshots")  # noqa: F821

    def __repr__(self) -> str:
        return f"<MarketSnapshot id={self.id} market_id={self.market_id} ts={self.timestamp}>"
