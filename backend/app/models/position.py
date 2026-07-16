"""
Position model — Layer 8: Position Tracking.

One row per FILLED entry order. Tracks the lifecycle of a paper-mode long
position from open (entry_price = fill_price) through live PnL updates to
close.

Status lifecycle:
  OPEN → CLOSED

PnL semantics (paper mode):
  LONG_YES: current_price = yes_mid
  LONG_NO:  current_price = 1 - yes_mid

  unrealized_pnl = quantity * (current_price - entry_price)
  realized_pnl   = quantity * (exit_price    - entry_price) - total_fee_usdc

Layer 12 audit trail (all set on CLOSED):
  close_reason      — WHY was it closed (EXIT_PROFIT_TARGET, EXIT_STOP_LOSS, …)
  exit_price        — AT WHAT PRICE was it closed (bid-side, never mid)
  close_decision_id — WHICH TradeDecision triggered the close
  close_order_id    — WHICH Order executed the close

Phase 4 additions:
  peak_pnl_usdc  — highest unrealized_pnl seen while OPEN (for trailing stop)
  total_fee_usdc — sum of entry + exit fees deducted from realized_pnl

Multi-entry / multi-exit additions (RESUME CARD PNL + multi-lot):
  Each row remains exactly one entry fill ("lot"). Multiple lots are allowed
  per condition_id — see RiskEngine for the entry-admission rules that
  replace the old single-position-per-market block.

  entry_sequence     — 1-based order this lot was opened within its condition_id
  scale_in_reason    — why an additional (sequence > 1) lot was opened
  remaining_quantity — quantity not yet closed; supports partial exits.
                       status transitions OPEN -> PARTIAL (0 < remaining < qty)
                       -> CLOSED (remaining == 0). realized_pnl accumulates
                       across every partial close of this lot.
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
        comment="FK → orders.id (entry order; one position per fill)",
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
        comment="Number of tokens / contracts (original entry size — never overwritten)",
    )
    remaining_quantity: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Quantity not yet closed. Starts == quantity; 0 when fully closed.",
    )
    entry_sequence: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="1-based sequence of this lot among all lots for condition_id",
    )
    scale_in_reason: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment=(
            "Set when entry_sequence > 1: SIGNAL_STRENGTHENED | "
            "CONFIDENCE_INCREASED | BETTER_ENTRY_PRICE | ORDER_FLOW_CONFIRMED | "
            "PARTIAL_ALLOCATION | REBALANCE | REENTRY_AFTER_PARTIAL_EXIT"
        ),
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
        comment="quantity * (exit_price - entry_price) - total_fee_usdc, set on CLOSED",
    )

    # ── Phase 4: Trailing stop support ────────────────────────────────────────
    peak_pnl_usdc: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None,
        comment="Highest unrealized_pnl seen while OPEN — used by trailing stop",
    )

    # ── Phase 4: Fee simulation ────────────────────────────────────────────────
    total_fee_usdc: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0,
        comment="Sum of entry + exit fees deducted from realized_pnl",
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="OPEN",
        comment="OPEN | PARTIAL | CLOSED",
    )

    # ── Layer 12: exit audit trail ─────────────────────────────────────────────
    close_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="Why the position was closed (EXIT_PROFIT_TARGET, EXIT_STOP_LOSS, …)",
    )
    exit_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Executable bid-side price used to close (never mid)",
    )
    close_decision_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="FK → trade_decisions.id of the CLOSE_POSITION decision",
    )
    close_order_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="FK → orders.id of the exit SELL_YES / SELL_NO order",
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
