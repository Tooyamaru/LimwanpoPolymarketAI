"""
Universe API endpoints — Sprint 7.

GET  /api/v1/universe           — all markets in the universe
GET  /api/v1/universe/active    — active markets only
GET  /api/v1/universe/upcoming  — upcoming markets only
GET  /api/v1/universe/stats     — counts by asset × timeframe × status
POST /api/v1/universe/sync      — trigger an immediate sync

All list responses include computed lifecycle fields:
  lifecycle_state, execution_allowed, is_pre_market, is_active_market,
  is_expired, display_status, data_mode
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.universe_repository import (
    get_active_universe,
    get_all_universe,
    get_upcoming_universe,
    get_universe_stats,
)
from app.schemas.universe import (
    AssetStats,
    SyncResponse,
    TimeframeStats,
    UniverseMarketResponse,
    UniverseStatsResponse,
)
from app.services.market_universe_service import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_INVALID,
    LIFECYCLE_PRE_MARKET,
    LIFECYCLE_RESOLUTION_PENDING,
    LIFECYCLE_RESOLVED,
    get_market_lifecycle_state,
)

router = APIRouter(prefix="/universe", tags=["universe"])


# ── Lifecycle annotation helper ───────────────────────────────────────────────

def _annotate_lifecycle(m) -> UniverseMarketResponse:
    """
    Build a UniverseMarketResponse from an ORM row and populate all lifecycle
    state fields (computed from start_time/end_time, not stored in DB).

    Also computes timing fields for accurate frontend countdown (spec §17):
      server_time       — ISO UTC string of when this response was built.
      countdown_seconds — max(0, floor(end_time - server_time)) in seconds.
      countdown_source  — "market_end_time" | "missing".
      countdown_data_stale — True when end_time is absent or invalid.
    """
    now = datetime.now(timezone.utc)
    server_time_iso = now.isoformat()

    # ── Countdown fields ───────────────────────────────────────────────────────
    end_time = m.end_time
    if end_time is not None:
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        remaining = (end_time - now).total_seconds()
        countdown_seconds = max(0, int(remaining))
        countdown_source = "market_end_time"
        countdown_data_stale = False
    else:
        countdown_seconds = None
        countdown_source = "missing"
        countdown_data_stale = True

    resp = UniverseMarketResponse.model_validate(m)
    lc = get_market_lifecycle_state(m)

    is_active   = lc == LIFECYCLE_ACTIVE
    is_pre      = lc == LIFECYCLE_PRE_MARKET
    is_exp      = lc in (LIFECYCLE_EXPIRED, LIFECYCLE_RESOLUTION_PENDING)
    is_resolved = lc == LIFECYCLE_RESOLVED

    if lc == LIFECYCLE_PRE_MARKET:
        display = "PRE-MARKET"
        mode    = "SEED"
    elif lc == LIFECYCLE_ACTIVE:
        display = "ACTIVE"
        mode    = "LIVE"
    elif lc in (LIFECYCLE_EXPIRED, LIFECYCLE_RESOLUTION_PENDING):
        display = "EXPIRED"
        mode    = "FINAL"
    elif lc == LIFECYCLE_RESOLVED:
        display = "RESOLVED"
        mode    = "FINAL"
    else:  # INVALID_TIME_STATE
        display = "UNKNOWN"
        mode    = "SEED"

    return resp.model_copy(update={
        "lifecycle_state":       lc,
        "execution_allowed":     is_active,
        "is_pre_market":         is_pre,
        "is_active_market":      is_active,
        "is_expired":            is_exp,
        "display_status":        display,
        "data_mode":             mode,
        "server_time":           server_time_iso,
        "countdown_seconds":     countdown_seconds,
        "countdown_source":      countdown_source,
        "countdown_data_stale":  countdown_data_stale,
    })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UniverseMarketResponse],
    summary="List all markets in the universe",
)
async def list_universe(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_all_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/active",
    response_model=list[UniverseMarketResponse],
    summary="List active universe markets",
)
async def list_active(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_active_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/upcoming",
    response_model=list[UniverseMarketResponse],
    summary="List upcoming universe markets",
)
async def list_upcoming(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_upcoming_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/stats",
    response_model=UniverseStatsResponse,
    summary="Universe statistics by asset, timeframe, and status",
)
async def universe_stats(
    session: AsyncSession = Depends(get_db_session),
) -> UniverseStatsResponse:
    raw = await get_universe_stats(session)

    by_asset: dict[str, AssetStats] = {}
    for asset, data in raw["by_asset"].items():
        by_tf: dict[str, TimeframeStats] = {}
        for tf, counts in data["by_timeframe"].items():
            by_tf[tf] = TimeframeStats(
                active=counts.get("active", 0),
                upcoming=counts.get("upcoming", 0),
                expired=counts.get("expired", 0),
            )
        by_asset[asset] = AssetStats(total=data["total"], by_timeframe=by_tf)

    return UniverseStatsResponse(
        total=raw["total"],
        by_status=raw["by_status"],
        by_asset=by_asset,
        by_timeframe=raw["by_timeframe"],
    )


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Trigger an immediate universe sync",
)
async def trigger_sync(request: Request) -> SyncResponse:
    """
    Runs a full universe sync right now.
    Uses the shared MarketUniverseService from app.state if available,
    otherwise creates a temporary one.
    """
    universe_service = getattr(request.app.state, "universe_service", None)

    if universe_service is not None:
        result = await universe_service.sync()
    else:
        from app.services.market_universe_service import MarketUniverseService
        svc = MarketUniverseService()
        try:
            result = await svc.sync()
        finally:
            await svc.close()

    return SyncResponse(**result)
