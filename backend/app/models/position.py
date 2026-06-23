"""
Position model — Layer 8: Position Tracking.

One row per FILLED order. Tracks the lifecycle of a paper-mode long position
from open (entry_price = fill_price) through live PnL updates to close.

Status lifecycle:
  OPEN → CLOSED

PnL semantics (paper mode):
  LONG_YES: current_price = yes_mid
  LONG_NO:  current_price = 1 - yes_mid

  unrealized_pnl = quantity * (current_price - entry_price)
  realized_pnl   = quantity * (close_price  - entry_price)  [set on CLOSED]
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_position_order_id", "order_id", unique=True),
        Index("ix_position_condition_id", "condition_id"),
        Index("ix_position_status", "status"),
        Index("ix_position_asset_tf", "asset", "timeframe"),
        Index("ix_position_opened_at", "opened_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True,
        comment="FK → orders.id (one position per fill)",
    )
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    side: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="LONG_YES | LONG_NO",
    )
    quantity: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Number of tokens / contracts",
    )

    entry_price: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Fill price at position open",
    )
    current_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Latest market price (LONG_YES=yes_mid, LONG_NO=1-yes_mid)",
    )

    unrealized_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="quantity * (current_price - entry_price)",
    )
    realized_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="quantity * (close_price - entry_price), set on CLOSED",
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="OPEN",
        comment="OPEN | CLOSED",
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        pnl = f"{self.unrealized_pnl:+.4f}" if self.unrealized_pnl is not None else "n/a"
        return (
            f"<Position id={self.id} {self.asset}/{self.timeframe} "
            f"side={self.side} entry={self.entry_price} upnl={pnl} status={self.status}>"
        )
