from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DiscoveryRun(Base):
    """Stores per-run diagnostics from the market discovery engine."""

    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    total_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    btc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eth_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sol_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xrp_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<DiscoveryRun id={self.id} scanned={self.total_scanned} "
            f"matched={self.total_matched} at={self.run_at}>"
        )
