"""
Trend router — Decision Engine pipeline, stage 3 (Trend).

GET /trend          — current trend score for every scored asset/timeframe
GET /trend/{asset}/{timeframe} — single pair detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import trend_repository as repo
from app.schemas.trend import TrendScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/trend", tags=["decision-engine"])


@router.get("", response_model=list[TrendScoreResponse])
async def get_all_trend_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current trend score for every asset/timeframe pair."""
    rows = await repo.get_all_trend_scores(session)
    return [TrendScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}/{timeframe}", response_model=TrendScoreResponse)
async def get_trend_score(
    asset: str,
    timeframe: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current trend score for a specific asset/timeframe pair."""
    row = await repo.get_trend_score(session, asset.upper(), timeframe)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No trend score found for {asset}/{timeframe}",
        )
    return TrendScoreResponse.model_validate(row)
