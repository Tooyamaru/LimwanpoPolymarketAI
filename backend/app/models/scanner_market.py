from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScannerMarket(Base):
    """
    Active market universe built by the scanner engine.

    Every row represents one Polymarket market that has been matched to a
    tracked asset + timeframe pair. Transparency fields record exactly WHY
    the market was matched — mandatory for auditability.
    """

    __tablename__ = "scanner_markets"
    __table_args__ = (
        UniqueConstraint("market_id", name="uq_scanner_markets_market_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    market_id: Mapped[str] = mapped_column(String(256), nullable=False)
    health_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # ── Transparency fields (Task 8) ─────────────────────────────────────────
    raw_title: Mapped[str] = mapped_column(String(512), nullable=False)
    matching_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    detected_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    detected_timeframe: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ScannerMarket id={self.id} asset={self.asset} "
            f"tf={self.timeframe} status={self.health_status}>"
        )
