"""
Markets API endpoints — Sprint 2.

GET /api/v1/markets          — list all markets
GET /api/v1/markets/active   — active markets only
GET /api/v1/markets/latest   — latest snapshots across all markets
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.market_repository import (
    get_active_markets,
    get_latest_snapshots,
)
from sqlalchemy import select
from app.models.market import Market
from app.models.market_snapshot import MarketSnapshot

router = APIRouter(prefix="/markets", tags=["markets"])


# ── Response schemas ──────────────────────────────────────────────────────────

class MarketResponse(BaseModel):
    id: int
    asset: str
    timeframe: str
    polymarket_market_id: str
    title: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str

    model_config = {"from_attributes": True}


class SnapshotResponse(BaseModel):
    id: int
    market_id: int
    timestamp: datetime
    yes_price: Optional[float]
    no_price: Optional[float]
    liquidity: Optional[float]
    volume: Optional[float]
    binance_price: Optional[float]

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MarketResponse], summary="List all markets")
async def list_markets(
    session: AsyncSession = Depends(get_db_session),
) -> list[MarketResponse]:
    result = await session.execute(
        select(Market).order_by(Market.asset, Market.timeframe)
    )
    markets = result.scalars().all()
    return [MarketResponse.model_validate(m) for m in markets]


@router.get("/active", response_model=list[MarketResponse], summary="List active markets")
async def list_active_markets(
    session: AsyncSession = Depends(get_db_session),
) -> list[MarketResponse]:
    markets = await get_active_markets(session)
    return [MarketResponse.model_validate(m) for m in markets]


@router.get(
    "/latest",
    response_model=list[SnapshotResponse],
    summary="Latest snapshots across all markets",
)
async def list_latest_snapshots(
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
) -> list[SnapshotResponse]:
    snapshots = await get_latest_snapshots(session, limit=limit)
    return [SnapshotResponse.model_validate(s) for s in snapshots]
