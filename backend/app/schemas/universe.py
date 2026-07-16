"""
Universe response schemas — Layer 3: Universe Sync / Sprint 7.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


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
