"""
MarketPriceSnapshot model — Sprint 9.

One row per price snapshot captured from the Polymarket CLOB.
Stores best bid/ask for YES and NO tokens, mid prices, spreads,
volume, and liquidity at the moment of capture.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    market_universe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("market_universe.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    yes_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    no_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    yes_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    no_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    no_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    spread_yes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_no: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketPriceSnapshot id={self.id} condition_id={self.condition_id[:12]}... "
            f"yes_mid={self.yes_mid} captured_at={self.captured_at}>"
        )
