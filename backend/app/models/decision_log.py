"""
DecisionLog model — Decision Engine pipeline, final stage (Decision).

Append-only log — every Decision Engine cycle writes one row per active
market, mirroring the TradeDecision append-only pattern. This is a
*read-only analytical* pipeline: DecisionLog rows are informational output,
never consumed by Strategy/Risk/Execution engines and never mutate any
market/trading data.

Phase Next: Decision Engine Intelligence Upgrade
- consensus_score, agreement_level, conflict_detected (Phase 1 Consensus Engine)
- entry_quality_score (Phase 3 Entry Quality Engine)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DecisionLog(Base):
    __tablename__ = "decision_logs"
    __table_args__ = (
        Index("ix_decision_condition_id", "condition_id"),
        Index("ix_decision_asset_tf", "asset", "timeframe"),
        Index("ix_decision_created_at", "created_at"),
        Index("ix_decision_decision", "decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    decision: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="BUY_YES | BUY_NO | WAIT",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 overall weighted confidence in the decision (Phase 4 Confidence Engine)",
    )
    vote_score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Weighted directional vote sum in [-1, 1]; >0 leans YES, <0 leans NO",
    )

    # ── Phase 1: Consensus Engine ────────────────────────────────────────────
    consensus_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — agreement strength among voting engines (100 = unanimous)",
    )
    agreement_level: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-1 — fraction of directional vote-weight on the winning side",
    )
    conflict_detected: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True,
        comment="True when >30% of vote-weight is on the opposing side (strong disagreement)",
    )

    # ── Phase 3: Entry Quality Engine ────────────────────────────────────────
    entry_quality_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0-100 — is this a good moment to enter? (spread, price, liquidity, opportunity)",
    )

    # ── Per-engine breakdown (read-only snapshot at decision time) ───────────
    signal_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    signal_regime: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    momentum_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    momentum_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    trend_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trend_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    volatility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatility_regime: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    opportunity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opportunity_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_gated: Mapped[Optional[bool]] = mapped_column(nullable=True)

    # ── Phase Next: Polymarket-first reasoning engines ───────────────────────
    market_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_quality: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    market_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_risk: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    market_context_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    market_context_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    orderbook_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    orderbook_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    funding_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    funding_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    news_sentiment: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    news_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    supporting_engines: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Comma-joined list of engines that contributed to this decision",
    )

    reasons: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Newline-joined reasoning chain from every step (Phases 1-10)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionLog {self.asset}/{self.timeframe} "
            f"decision={self.decision} confidence={self.confidence:.1f} "
            f"consensus={self.consensus_score} conflict={self.conflict_detected}>"
        )
