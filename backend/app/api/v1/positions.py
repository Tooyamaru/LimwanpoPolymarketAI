"""
Positions router — Layer 8: Position Tracking.

GET /positions           — all positions (newest first)
GET /positions/open      — positions with status OPEN
GET /positions/closed    — positions with status CLOSED (newest first)
GET /positions/stats     — aggregate PnL and count statistics
GET /positions/{id}      — single position detail
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import position_repository as repo
from app.schemas.position import PositionResponse, PositionStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PositionResponse])
async def get_positions(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: OPEN | CLOSED",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all positions, newest first. Optionally filter by status."""
    rows = await repo.get_positions(session, status_filter=status, limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/open", response_model=list[PositionResponse])
async def get_open_positions(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all OPEN positions ordered by open time ascending."""
    rows = await repo.get_open_positions(session, limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/closed", response_model=list[PositionResponse])
async def get_closed_positions(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return CLOSED positions, newest first. Used by the dashboard last-trade widget."""
    rows = await repo.get_positions(session, status_filter="CLOSED", limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=PositionStatsResponse)
async def get_position_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate position counts and PnL statistics."""
    stats = await repo.get_position_stats(session)
    return PositionStatsResponse(**stats)


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Return a single position by its ID."""
    pos = await repo.get_position(session, position_id)
    if pos is None:
        raise HTTPException(
            status_code=404,
            detail=f"Position id={position_id} not found",
        )
    return PositionResponse.model_validate(pos)
