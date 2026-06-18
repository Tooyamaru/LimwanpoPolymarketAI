from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventClassification(Base):
    """
    Stores the classification for every asset+timeframe matched market.

    Every row has full transparency: raw title, which rule fired, what type was
    assigned, and the confidence score.  Only UPDOWN rows are promoted to the
    scanner_markets universe.
    """

    __tablename__ = "event_classifications"
    __table_args__ = (
        UniqueConstraint("market_id", name="uq_event_classifications_market_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_title: Mapped[str] = mapped_column(String(512), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<EventClassification id={self.id} market_id={self.market_id!r} "
            f"type={self.event_type} conf={self.confidence:.2f}>"
        )
