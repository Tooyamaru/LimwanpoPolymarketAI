"""API — Portfolio Allocation Intelligence (Priority 4)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services.portfolio_allocation_service import (
    MAX_CONCURRENT_POSITIONS,
    MIN_ALLOCATION_SCORE,
    PortfolioAllocationService,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/portfolio-allocation", tags=["portfolio-allocation"])

_svc = PortfolioAllocationService()


@router.get("")
async def get_portfolio_allocation(
    max_concurrent: int = Query(MAX_CONCURRENT_POSITIONS, ge=1, le=50),
    min_score: float = Query(MIN_ALLOCATION_SCORE, ge=0.0, le=100.0),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Rank all active opportunities by composite score and return
    ENTER / DEFER / SKIP decisions with full reasoning.
    """
    return await _svc.get_ranked_summary(session, max_concurrent=max_concurrent, min_score=min_score)
