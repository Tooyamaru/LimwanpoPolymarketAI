"""
Order model — Layer 7: Execution Engine (Paper Mode).

Append-only log of simulated order fills.  Each row is created when the
Execution Engine processes a PENDING OPEN_LONG_YES / OPEN_LONG_NO trade
decision.  In paper mode every order is filled immediately at the best
available price with no slippage.

Paper-mode fill logic:
  OPEN_LONG_YES → fill_price = yes_ask   (buy YES tokens at the ask)
  OPEN_LONG_NO  → fill_price = 1 - yes_bid  (buy NO tokens at implied ask)

Status lifecycle:
  PENDING → FILLED | CANCELLED | FAILED
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_order_decision_id", "decision_id"),
        Index("ix_order_condition_id", "condition_id"),
        Index("ix_order_status", "status"),
        Index("ix_order_asset_tf", "asset", "timeframe"),
        Index("ix_order_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Link back to the TradeDecision that triggered this order ──────────────
    decision_id: Mapped[int] = mapped_column(Integer, nullable=False)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    # ── Order parameters ──────────────────────────────────────────────────────
    side: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="LONG_YES | LONG_NO",
    )
    order_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MARKET",
        comment="MARKET (paper mode always uses market fills)",
    )
    quantity: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Number of contracts / tokens (paper: always 1.0)",
    )

    # ── Pricing ───────────────────────────────────────────────────────────────
    requested_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Price at which execution was requested (best ask / implied ask)",
    )
    filled_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Actual fill price (== requested_price in paper mode)",
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING",
        comment="PENDING | FILLED | CANCELLED | FAILED",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} {self.asset}/{self.timeframe} "
            f"side={self.side} price={self.filled_price} status={self.status}>"
        )
