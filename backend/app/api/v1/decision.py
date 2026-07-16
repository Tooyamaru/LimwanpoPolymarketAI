"""
Decision router — Decision Engine pipeline, final stage (Decision).

GET /decision              — most recent decision log rows
GET /decision/stats         — aggregate BUY_YES / BUY_NO / WAIT counts
GET /decision/{condition_id} — latest decision for a specific market
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import decision_repository as repo
from app.schemas.decision import DecisionLogResponse, DecisionStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/decision", tags=["decision-engine"])


@router.get("", response_model=list[DecisionLogResponse])
async def get_recent_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the most recent Decision Engine log rows, newest first."""
    rows = await repo.get_recent_decisions(session, limit=limit)
    return [DecisionLogResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=DecisionStatsResponse)
async def get_decision_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate BUY_YES / BUY_NO / WAIT counts across the latest decision per market."""
    stats = await repo.get_decision_stats(session)
    return DecisionStatsResponse(**stats)


@router.get("/{condition_id}", response_model=DecisionLogResponse)
async def get_latest_decision(
    condition_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the most recent decision for a specific condition_id."""
    row = await repo.get_latest_decision(session, condition_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No decision found for condition_id={condition_id}",
        )
    return DecisionLogResponse.model_validate(row)
