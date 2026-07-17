"""
MarketUniverse model — Sprint 7.

Represents a single binary market within a known Gamma Series
(e.g. btc-up-or-down-5m).  One row per market (condition_id).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Double, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketUniverse(Base):
    __tablename__ = "market_universe"
    __table_args__ = (
        UniqueConstraint("condition_id", name="uq_market_universe_condition_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    series_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    series_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)

    yes_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    no_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    question: Mapped[str] = mapped_column(String(1024), nullable=False)

    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )

    # ── Prediction Window (timestamp-slug discovery) ──────────────────────────
    # Parsed from the market question text; stored so selection never re-parses.
    prediction_window_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    prediction_window_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    prediction_window_source: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    prediction_window_validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Market Reference (Phase Next) ─────────────────────────────────────────
    # opening_price is fetched from Binance once at market discovery and stored
    # permanently.  The frontend reads this value instead of computing it.
    opening_price: Mapped[Optional[float]] = mapped_column(Double(), nullable=True)
    opening_price_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    opening_price_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reference_status: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, default="PENDING"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<MarketUniverse id={self.id} asset={self.asset} "
            f"tf={self.timeframe} status={self.status}>"
        )
