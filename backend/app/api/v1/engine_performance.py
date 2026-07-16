"""API — Engine Performance Tracking (Priority 2)."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import engine_performance_repository as ep_repo
from app.schemas.engine_performance import (
    EnginePerformanceResponse,
    EnginePerformanceSummaryResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/engine-performance", tags=["engine-performance"])


@router.get("", response_model=EnginePerformanceSummaryResponse)
async def get_engine_performance_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """All engine performance stats ranked by accuracy."""
    engines = await ep_repo.get_all_engine_performances(session)

    engines_with_acc = [e for e in engines if e.accuracy is not None]
    avg_accuracy = (
        round(sum(e.accuracy for e in engines_with_acc) / len(engines_with_acc), 2)
        if engines_with_acc else None
    )
    best  = max(engines_with_acc, key=lambda e: e.accuracy, default=None)
    worst = min(engines_with_acc, key=lambda e: e.accuracy, default=None)

    return EnginePerformanceSummaryResponse(
        total_engines_tracked=len(engines),
        avg_accuracy=avg_accuracy,
        best_engine=best.engine_name if best else None,
        worst_engine=worst.engine_name if worst else None,
        engines=engines,
    )


@router.get("/{engine_name}", response_model=Optional[EnginePerformanceResponse])
async def get_single_engine_performance(
    engine_name: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Performance stats for a single engine by name."""
    return await ep_repo.get_engine_performance(session, engine_name)
