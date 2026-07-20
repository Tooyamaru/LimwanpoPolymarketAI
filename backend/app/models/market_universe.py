"""
MarketUniverse model — Sprint 7.

Represents a single binary market within a known Gamma Series
(e.g. btc-up-or-down-5m).  One row per market (condition_id).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Double, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketUniverse(Base):
    __tablename__ = "market_universe"
    __table_args__ = (
        UniqueConstraint("condition_id", name="uq_market_universe_condition_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    series_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    series_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    # Exact rolling 5-minute event slug: {asset}-updown-5m-{unix_slot}
    # e.g. "btc-updown-5m-1784271300"  (distinct from series_slug)
    event_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False)

    yes_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    no_token_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    question: Mapped[str] = mapped_column(String(1024), nullable=False)

    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )

    # ── Prediction Window (timestamp-slug discovery) ──────────────────────────
    # Parsed from the market question text; stored so selection never re-parses.
    prediction_window_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    prediction_window_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    prediction_window_source: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    prediction_window_validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Market Reference (Phase Next) ─────────────────────────────────────────
    # opening_price is fetched from Binance once at market discovery and stored
    # permanently.  The frontend reads this value instead of computing it.
    opening_price: Mapped[Optional[float]] = mapped_column(Double(), nullable=True)
    opening_price_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    opening_price_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reference_status: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, default="PENDING"
    )

    # ── Target / Price to Beat (Chainlink integration) ─────────────────────────
    # target_price is the canonical Price to Beat, set by the target_worker from
    # an official Polymarket source (Gamma API priceToBeat field, or if absent a
    # verified Chainlink RTDS observation at prediction_window_start).
    #
    # Integrity gate (CHAINLINK_INTEGRITY_GATE_ENABLED=True):
    #   OPEN_LONG_* is BLOCKED unless target_verified=True.
    #   Exit / settlement decisions bypass this gate entirely.
    #
    # Immutable once locked: target_worker stops retrying when target_verified=True.
    target_price: Mapped[Optional[float]] = mapped_column(Double(), nullable=True)
    target_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_raw_source: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    target_source_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_event_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    target_condition_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    target_verified: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    target_stale: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )
    target_validation_error: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    # ── Official PTB API source traceability ──────────────────────────────────
    # Persisted when target_source = POLYMARKET_CRYPTO_PRICE_API.
    # target_source_url:        full request URL including all query parameters
    # target_source_field_path: JSON field name where the value was read ("openPrice")
    target_source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    target_source_field_path: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # ── Target reconciliation diagnostics (spec §5 / §10) ─────────────────────
    # Chainlink candidate: which tick-selection rule was used before official
    # reconciliation (e.g. "tick_at_or_before", "nearest_tick", "none_available")
    target_candidate_rule: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    # Comparison value from official Polymarket source (Gamma API), stored even
    # when it differs from the Chainlink candidate so delta can be audited.
    target_official_comparison_value: Mapped[Optional[float]] = mapped_column(
        Double(), nullable=True
    )
    # candidate value − official value (signed); None until both are known.
    target_difference: Mapped[Optional[float]] = mapped_column(
        Double(), nullable=True
    )
    # Retry bookkeeping — target worker updates these on every attempt.
    target_retry_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    target_last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_last_error: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<MarketUniverse id={self.id} asset={self.asset} "
            f"tf={self.timeframe} status={self.status}>"
        )
