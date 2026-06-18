from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (
        UniqueConstraint("polymarket_market_id", name="uq_markets_polymarket_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    polymarket_market_id: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    snapshots: Mapped[list["MarketSnapshot"]] = relationship(  # noqa: F821
        "MarketSnapshot", back_populates="market", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Market id={self.id} asset={self.asset} tf={self.timeframe}>"
