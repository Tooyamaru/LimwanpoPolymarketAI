"""API — Outcome Learning (Priority 1 + Priority 5 Feedback Loop)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import outcome_learning_repository as ol_repo
from app.schemas.outcome_learning import (
    OutcomeLearningResponse,
    OutcomeLearningStatsResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/outcome-learning", tags=["outcome-learning"])


@router.get("", response_model=list[OutcomeLearningResponse])
async def list_outcomes(
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the most recent outcome learning evaluations."""
    return await ol_repo.get_recent_outcomes(session, limit=limit)


@router.get("/stats", response_model=OutcomeLearningStatsResponse)
async def outcome_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Aggregate outcome learning statistics — accuracy, calibration, feedback."""
    return await ol_repo.get_outcome_stats(session)


@router.get("/{condition_id}", response_model=Optional[OutcomeLearningResponse])
async def get_outcome(
    condition_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return outcome learning record for a specific market (by condition_id)."""
    return await ol_repo.get_outcome_by_condition_id(session, condition_id)
