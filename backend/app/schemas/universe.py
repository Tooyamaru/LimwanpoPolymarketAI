"""
Universe response schemas — Layer 3: Universe Sync / Sprint 7.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class UniverseMarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    series_slug: str
    series_id: Optional[str]
    event_id: Optional[str]
    condition_id: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]
    question: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str
    # Market Reference (Phase Next) — opening price fetched from Binance once at discovery
    opening_price: Optional[float] = None
    opening_price_source: Optional[str] = None
    opening_price_timestamp: Optional[datetime] = None
    reference_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # ── Target / Price to Beat (Chainlink integration) ─────────────────────────
    # Set by target_worker from official Polymarket source (Gamma API).
    # target_verified=True is required before entry decisions are allowed.
    target_price: Optional[float] = None
    target_source: Optional[str] = None
    target_raw_source: Optional[str] = None
    target_source_timestamp: Optional[datetime] = None
    target_locked_at: Optional[datetime] = None
    target_event_slug: Optional[str] = None
    target_condition_id: Optional[str] = None
    target_verified: bool = False
    target_stale: bool = True
    target_validation_error: Optional[str] = None
    # Official PTB API source traceability (populated when source = POLYMARKET_CRYPTO_PRICE_API)
    target_source_url: Optional[str] = None
    target_source_field_path: Optional[str] = None

    # ── Lifecycle state fields (computed at API layer, not stored in DB) ─────────
    # lifecycle_state: canonical state derived from start_time/end_time/now
    #   PRE_MARKET        — now < start_time; seed data visible but no execution
    #   ACTIVE            — start_time <= now < end_time; live trading window
    #   EXPIRED           — now >= end_time; no new entry allowed
    #   RESOLUTION_PENDING — expired, awaiting Polymarket resolution
    #   RESOLVED          — direct resolution confirmed
    #   INVALID_TIME_STATE — start_time or end_time missing/contradictory
    lifecycle_state: str = "ACTIVE"
    # execution_allowed: true only when lifecycle_state == ACTIVE
    execution_allowed: bool = True
    is_pre_market: bool = False
    is_active_market: bool = True
    is_expired: bool = False
    # display_status: human-readable label for dashboard/frontend
    display_status: str = "ACTIVE"
    # data_mode: SEED (pre-market book), LIVE (active window), FINAL (post-expiry)
    data_mode: str = "LIVE"

    # ── Timing fields for accurate frontend countdown (spec §17) ────────────────
    # server_time:          ISO UTC string of when this response was generated.
    #                       Frontend computes server_offset_ms = server_time - Date.now()
    #                       then uses (Date.now() + offset) for drift-free countdown.
    # countdown_seconds:    max(0, floor(end_time - server_time)) in seconds.
    #                       Frontend re-syncs this every poll cycle.
    # countdown_source:     "market_end_time" — exact Polymarket condition end_time used.
    #                       "missing"         — no valid end_time available.
    # countdown_data_stale: True when end_time is absent or contradictory.
    #                       Frontend must show "SYNCING" (not a fake timer) in this case.
    server_time: Optional[str] = None
    countdown_seconds: Optional[int] = None
    countdown_source: str = "market_end_time"
    countdown_data_stale: bool = False

    # ── Extended countdown fields (spec §12) ────────────────────────────────
    # countdown_mode:          STARTS_IN | ENDS_IN | RESOLVING | SYNCING | STATIC
    # prediction_window_start: ISO UTC — when the market trading window opens (= start_time)
    # prediction_window_end:   ISO UTC — when the market trading window closes (= end_time)
    # countdown_target:        ISO UTC — the timestamp the frontend counts down to
    # trading_open_time:       ISO UTC — alias for prediction_window_start
    countdown_mode: Optional[str] = None
    prediction_window_start: Optional[str] = None
    prediction_window_end: Optional[str] = None
    prediction_window_source: Optional[str] = None
    countdown_target: Optional[str] = None
    trading_open_time: Optional[str] = None
    # Slug fields — exact rolling 5m event identity
    event_slug: Optional[str] = None
    market_slot_timestamp: Optional[int] = None

    model_config = {"from_attributes": True}

    @field_validator(
        "prediction_window_start",
        "prediction_window_end",
        "countdown_target",
        "trading_open_time",
        mode="before",
    )
    @classmethod
    def _coerce_dt_to_str(cls, v: object) -> Optional[str]:
        """ORM model stores these as datetime; schema exposes them as ISO strings."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v  # type: ignore[return-value]

    @field_validator(
        "event_slug",
        "prediction_window_source",
        "target_source",
        "target_raw_source",
        "target_event_slug",
        "target_condition_id",
        "target_validation_error",
        "target_source_url",
        "target_source_field_path",
        mode="before",
    )
    @classmethod
    def _coerce_str_or_none(cls, v: object) -> Optional[str]:
        """Return the value as-is if it's a str or None; coerce anything else to None.
        This prevents MagicMock objects (used in test helpers) from failing str validation."""
        if v is None or isinstance(v, str):
            return v
        return None

    @field_validator(
        "market_slot_timestamp",
        mode="before",
    )
    @classmethod
    def _coerce_int_or_none(cls, v: object) -> Optional[int]:
        """Return the value as-is if it's an int or None; coerce anything else to None."""
        if v is None or isinstance(v, int):
            return v
        return None

    @field_validator(
        "target_verified",
        "target_stale",
        mode="before",
    )
    @classmethod
    def _coerce_bool(cls, v: object) -> bool:
        """Coerce non-bool values (e.g. MagicMock) to False for safety."""
        if isinstance(v, bool):
            return v
        return False

    @field_validator(
        "target_price",
        mode="before",
    )
    @classmethod
    def _coerce_float_or_none(cls, v: object) -> Optional[float]:
        """Coerce non-float/None values to None."""
        if v is None or isinstance(v, (int, float)):
            return v
        return None


class TimeframeStats(BaseModel):
    active: int
    upcoming: int
    expired: int


class AssetStats(BaseModel):
    total: int
    by_timeframe: dict[str, TimeframeStats]


class UniverseStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_asset: dict[str, AssetStats]
    by_timeframe: dict[str, dict[str, int]]


class SyncResponse(BaseModel):
    synced_at: str
    duration_ms: float
    series_processed: int
    markets_upserted: int
    markets_expired_by_time: int
    # Gamma ingestion quality classification (added alongside SSL fix)
    gamma_status: str = "UNKNOWN"        # GAMMA_OK | GAMMA_PARTIAL_SUCCESS | GAMMA_EMPTY_RESPONSE | GAMMA_UNREACHABLE | GAMMA_SSL_ERROR
    gamma_series_ok: int = 0             # series that returned ≥1 market
    gamma_series_empty: int = 0          # series reachable but returned 0 events
    gamma_series_failed: int = 0         # series that raised an exception
    errors: list[str]
