"""
Momentum router — Decision Engine pipeline, stage 2 (Momentum).

GET /momentum          — current momentum score for every scored asset/timeframe
GET /momentum/{asset}/{timeframe} — single pair detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import momentum_repository as repo
from app.schemas.momentum import MomentumScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/momentum", tags=["decision-engine"])


@router.get("", response_model=list[MomentumScoreResponse])
async def get_all_momentum_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current momentum score for every asset/timeframe pair."""
    rows = await repo.get_all_momentum_scores(session)
    return [MomentumScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}/{timeframe}", response_model=MomentumScoreResponse)
async def get_momentum_score(
    asset: str,
    timeframe: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current momentum score for a specific asset/timeframe pair."""
    row = await repo.get_momentum_score(session, asset.upper(), timeframe)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No momentum score found for {asset}/{timeframe}",
        )
    return MomentumScoreResponse.model_validate(row)
