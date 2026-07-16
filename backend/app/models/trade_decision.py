"""
TradeDecision model — Layer 6: Strategy Engine.

One row per strategy evaluation event. Unlike Opportunity (which UPSERTs to
one row per market), TradeDecision is an append-only log — every engine cycle
that produces a non-SKIP decision writes a new row.  This preserves a full
history of strategy signals for back-testing and monitoring.

Decision types:
  OPEN_LONG_YES  — score >= 40 and direction == BUY_YES
  OPEN_LONG_NO   — score >= 40 and direction == BUY_NO
  WATCH          — score 20–39 (any direction)
  SKIP           — score < 20 OR spread > 0.02

Status lifecycle:
  PENDING → RISK_APPROVED → EXECUTED   (normal path)
  PENDING → BLOCKED                    (risk rule tripped)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TradeDecision(Base):
    __tablename__ = "trade_decisions"
    __table_args__ = (
        Index("ix_td_condition_id", "condition_id"),
        Index("ix_td_decision", "decision"),
        Index("ix_td_asset_tf", "asset", "timeframe"),
        Index("ix_td_decided_at", "decided_at"),
        Index("ix_td_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    # ── Strategy output ────────────────────────────────────────────────────────
    decision: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="OPEN_LONG_YES | OPEN_LONG_NO | WATCH | SKIP",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING",
        comment="PENDING | RISK_APPROVED | BLOCKED | EXECUTED",
    )

    # ── Inputs from Opportunity Engine ────────────────────────────────────────
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BUY_YES | BUY_NO | NEUTRAL",
    )

    yes_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_yes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Skip reason (populated when decision == SKIP) ─────────────────────────
    skip_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="LOW_SCORE | HIGH_SPREAD | NEUTRAL_DIRECTION",
    )

    # ── Layer 13: position sizing ─────────────────────────────────────────────
    position_size_usdc: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="USDC allocation computed by PositionSizingService",
    )

    # ── Exit engine fields (populated when decision == CLOSE_POSITION) ────────
    target_position_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="FK → positions.id; set for CLOSE_POSITION decisions",
    )
    exit_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="EXPIRY_EXIT | STOP_LOSS | PROFIT_TARGET | SIGNAL_INVALIDATION",
    )
    forced_exit_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment=(
            "Phase 10: authoritative exit price computed by ExitEngine for "
            "forced-expiry closes (from OutcomeLearning.final_yes_price / "
            "final_no_price, i.e. direct Polymarket resolution). When set, "
            "ExecutionEngine MUST use this price instead of recomputing from "
            "live (and potentially stale/expired) Opportunity bid/ask data."
        ),
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<TradeDecision id={self.id} {self.asset}/{self.timeframe} "
            f"decision={self.decision} score={self.opportunity_score:.1f}>"
        )
