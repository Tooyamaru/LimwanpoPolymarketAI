"""
Universe API endpoints — Sprint 7.

GET  /api/v1/universe           — all markets in the universe
GET  /api/v1/universe/active    — active markets only
GET  /api/v1/universe/upcoming  — upcoming markets only
GET  /api/v1/universe/stats     — counts by asset × timeframe × status
POST /api/v1/universe/sync      — trigger an immediate sync
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.universe_repository import (
    get_active_universe,
    get_all_universe,
    get_upcoming_universe,
    get_universe_stats,
)

router = APIRouter(prefix="/universe", tags=["universe"])


# ── Response schemas ───────────────────────────────────────────────────────────

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
    created_at: datetime
    updated_at: datetime

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
    errors: list[str]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UniverseMarketResponse],
    summary="List all markets in the universe",
)
async def list_universe(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_all_universe(session)
    return [UniverseMarketResponse.model_validate(m) for m in markets]


@router.get(
    "/active",
    response_model=list[UniverseMarketResponse],
    summary="List active universe markets",
)
async def list_active(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_active_universe(session)
    return [UniverseMarketResponse.model_validate(m) for m in markets]


@router.get(
    "/upcoming",
    response_model=list[UniverseMarketResponse],
    summary="List upcoming universe markets",
)
async def list_upcoming(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_upcoming_universe(session)
    return [UniverseMarketResponse.model_validate(m) for m in markets]


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
