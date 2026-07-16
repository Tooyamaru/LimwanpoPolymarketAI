"""
MarketQualityScore model — Polymarket Market Engine (Phase Next).

This is now the PRIMARY engine in the Decision Engine pipeline. Polymarket
is the source of truth: YES/NO bid/ask, spread, liquidity, volume,
countdown-to-expiry, and active/closed state are read as-is and never
recomputed or predicted. This engine only answers one question: is this
market currently worth trading at all (GOOD / AVERAGE / BAD)?

One row per condition_id — UPSERT on every cycle. Read-only with respect to
market_universe / market_price_snapshots — only reads them and writes here.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketQualityScore(Base):
    __tablename__ = "market_quality_scores"
    __table_args__ = (
        Index("ix_market_quality_condition_id", "condition_id", unique=True),
        Index("ix_market_quality_asset_tf", "asset", "timeframe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    market_score: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 composite market tradability score (spread/liquidity/volume/time-to-expiry/state)",
    )
    market_quality: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="GOOD | AVERAGE | BAD — is this market worth trading?",
    )
    market_confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0-100 — how much real Polymarket data backs this score (vs missing fields)",
    )
    market_risk: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="LOW | MEDIUM | HIGH — structural market risk (expiry proximity, spread, state)",
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Phase Next: Market Behaviour Engine ──────────────────────────────────
    market_behaviours: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Comma-joined behaviour labels e.g. 'Increasing Liquidity, Healthy Spread, Buy Pressure'",
    )

    yes_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yes_ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_yes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    seconds_to_expiry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    active: Mapped[Optional[bool]] = mapped_column(nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketQualityScore {self.asset}/{self.timeframe} "
            f"quality={self.market_quality} score={self.market_score:.1f}>"
        )
