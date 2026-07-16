"""
Order model — Layer 7: Execution Engine (Paper Mode).

Append-only log of simulated order fills.  Each row is created when the
Execution Engine processes a PENDING OPEN_LONG_YES / OPEN_LONG_NO trade
decision.  In paper mode every order is filled immediately at the best
available price with no slippage.

Paper-mode fill logic (no slippage, instant fill):
  OPEN_LONG_YES → fill_price = yes_ask   (buy YES tokens at the ask)
  OPEN_LONG_NO  → fill_price = 1 - yes_bid  (buy NO tokens at implied ask)

Status lifecycle:
  PENDING → FILLED | CANCELLED | FAILED

Phase 4 (Fee Simulation — Part D):
  entry_fee_usdc — fee charged at entry (fill_price × quantity × FEE_RATE)
  exit_fee_usdc  — fee charged at exit  (exit_price × quantity × FEE_RATE)
  Both default to 0.0 (paper mode).  Set POLYMARKET_FEE_RATE in settings to
  activate fee deduction from realized PnL.
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
        comment="LONG_YES | LONG_NO | SELL_YES | SELL_NO",
    )
    order_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MARKET",
        comment="MARKET (paper mode always uses market fills)",
    )
    quantity: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Number of contracts / tokens",
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

    # ── Fee simulation (Phase 4 Part D) ───────────────────────────────────────
    entry_fee_usdc: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0,
        comment="Fee at entry: filled_price × quantity × POLYMARKET_FEE_RATE",
    )
    exit_fee_usdc: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0,
        comment="Fee at exit: exit_price × quantity × POLYMARKET_FEE_RATE",
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
