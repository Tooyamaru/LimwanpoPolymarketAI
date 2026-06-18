"""
SourceValidationResult model — Sprint 5.

Stores per-market source tracing data from the source validation engine.
Every row represents one Polymarket market that was evaluated during a
validation run, with full lineage back to the raw CLOB response.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceValidationResult(Base):
    """
    Raw source tracing record for a single Polymarket market.

    Fields are populated directly from the CLOB API response so the
    calling code can always reconstruct the exact HTTP source for any
    stored market.
    """

    __tablename__ = "source_validation_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Run grouping ──────────────────────────────────────────────────────────
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # ── Source tracing (Task 1) ───────────────────────────────────────────────
    source_endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source_market_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ── Detection results ─────────────────────────────────────────────────────
    detected_asset: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True
    )
    detected_timeframe: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )
    is_updown_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    updown_keywords_found: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )
    matching_rule: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SourceValidationResult id={self.id} asset={self.detected_asset} "
            f"candidate={self.is_updown_candidate} run={self.run_id[:8]}>"
        )
