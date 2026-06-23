"""
Scanner API — Sprint 3.

GET /api/v1/scanner          — full scanner universe (all statuses)
GET /api/v1/scanner/active   — active markets only
GET /api/v1/scanner/stats    — aggregate counts by asset / status
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.scanner_repository import get_scanner_markets, get_scanner_stats

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ── Response schemas ──────────────────────────────────────────────────────────

class ScannerMarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    market_id: str
    health_status: str
    created_at: datetime
    raw_title: str
    matching_rule: str
    detected_asset: str
    detected_timeframe: str

    model_config = {"from_attributes": True}


class AssetBreakdown(BaseModel):
    BTC: int
    ETH: int
    SOL: int
    XRP: int


class ScannerStatsResponse(BaseModel):
    total: int
    active: int
    stale: int
    by_asset: AssetBreakdown


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ScannerMarketResponse],
    summary="Full scanner market universe",
)
async def list_scanner_markets(
    session: AsyncSession = Depends(get_db_session),
) -> list[ScannerMarketResponse]:
    markets = await get_scanner_markets(session)
    return [ScannerMarketResponse.model_validate(m) for m in markets]


@router.get(
    "/active",
    response_model=list[ScannerMarketResponse],
    summary="Active scanner markets only",
)
async def list_active_scanner_markets(
    session: AsyncSession = Depends(get_db_session),
) -> list[ScannerMarketResponse]:
    markets = await get_scanner_markets(session, health_status="active")
    return [ScannerMarketResponse.model_validate(m) for m in markets]


@router.get(
    "/stats",
    response_model=ScannerStatsResponse,
    summary="Aggregate scanner statistics",
)
async def scanner_stats(
    session: AsyncSession = Depends(get_db_session),
) -> ScannerStatsResponse:
    stats = await get_scanner_stats(session)
    return ScannerStatsResponse(
        total=stats["total"],
        active=stats["active"],
        stale=stats["stale"],
        by_asset=AssetBreakdown(**stats["by_asset"]),
    )
