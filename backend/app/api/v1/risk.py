"""
Risk router — Layer 9: Risk Engine.

GET /risk           — recent risk evaluation events (ALLOW + BLOCK)
GET /risk/blocked   — BLOCKED decisions only
GET /risk/stats     — aggregate counts and block rate
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import risk_repository as repo
from app.schemas.risk import RiskEventResponse, RiskStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("", response_model=list[RiskEventResponse])
async def get_risk_events(
    result: str | None = Query(
        default=None,
        description="Filter by result: ALLOW | BLOCK",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return recent risk evaluation events, newest first."""
    rows = await repo.get_risk_events(session, result_filter=result, limit=limit)
    return [RiskEventResponse.model_validate(r) for r in rows]


@router.get("/blocked", response_model=list[RiskEventResponse])
async def get_blocked_events(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return BLOCKED risk events only, newest first."""
    rows = await repo.get_blocked_events(session, limit=limit)
    return [RiskEventResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=RiskStatsResponse)
async def get_risk_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate risk evaluation counts and block rate."""
    stats = await repo.get_risk_stats(session)
    return RiskStatsResponse(**stats)
