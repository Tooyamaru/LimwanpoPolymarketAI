"""
RiskEvent model — Layer 9: Risk Engine.

One row per risk evaluation. Records whether a TradeDecision was ALLOWED
or BLOCKED together with a snapshot of the risk state at the moment of
evaluation.  Append-only — no UPSERTs.

Result values:
  ALLOW  — all rules passed; execution engine may proceed
  BLOCK  — one or more rules failed; decision is rejected

Reason values (first failing rule wins — Phase 12L):
  OPPOSITE_SIDE_CONFLICT   — open position exists on the opposite side
  MAX_EXPOSURE_PER_MARKET  — USDC exposure for this market >= MAX_EXPOSURE_PER_MARKET_USDC
  COOLDOWN_ACTIVE          — MIN_SECONDS_BETWEEN_ENTRIES not yet elapsed
  SCALE_IN_NO_IMPROVEMENT  — scale-in entry shows no score or price improvement
  INSUFFICIENT_CAPITAL     — available_capital - proposed_notional < MIN_AVAILABLE_CAPITAL_RESERVE_USDC
  DAILY_LOSS               — sum of today's unrealized PnL <= MAX_DAILY_LOSS
  DAILY_TRADES             — orders placed today >= MAX_DAILY_TRADES
  PORTFOLIO_EXPOSURE_LIMIT — total open exposure >= PORTFOLIO_MAX_EXPOSURE_USDC
  ASSET_EXPOSURE_LIMIT     — asset open exposure >= PORTFOLIO_MAX_PER_ASSET_USDC
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_event_decision_id", "decision_id"),
        Index("ix_risk_event_result", "result"),
        Index("ix_risk_event_asset_tf", "asset", "timeframe"),
        Index("ix_risk_event_checked_at", "checked_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    decision_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="FK → trade_decisions.id",
    )
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    result: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="ALLOW | BLOCK",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment=(
            "Phase 12L reasons: OPPOSITE_SIDE_CONFLICT | MAX_EXPOSURE_PER_MARKET | "
            "COOLDOWN_ACTIVE | SCALE_IN_NO_IMPROVEMENT | INSUFFICIENT_CAPITAL | "
            "DAILY_LOSS | DAILY_TRADES | PORTFOLIO_EXPOSURE_LIMIT | ASSET_EXPOSURE_LIMIT"
        ),
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Snapshot of risk state at check time ──────────────────────────────────
    open_positions_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Total OPEN positions at time of check",
    )
    daily_loss: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Sum of unrealized PnL for today's open positions",
    )
    daily_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Orders placed since midnight UTC today",
    )

    def __repr__(self) -> str:
        return (
            f"<RiskEvent id={self.id} decision_id={self.decision_id} "
            f"result={self.result} reason={self.reason}>"
        )
