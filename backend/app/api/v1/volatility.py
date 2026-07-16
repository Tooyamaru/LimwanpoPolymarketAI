"""
Volatility router — Decision Engine pipeline, stage 4 (Volatility).

GET /volatility          — current volatility score for every scored asset/timeframe
GET /volatility/{asset}/{timeframe} — single pair detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import volatility_repository as repo
from app.schemas.volatility import VolatilityScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/volatility", tags=["decision-engine"])


@router.get("", response_model=list[VolatilityScoreResponse])
async def get_all_volatility_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current volatility score for every asset/timeframe pair."""
    rows = await repo.get_all_volatility_scores(session)
    return [VolatilityScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}/{timeframe}", response_model=VolatilityScoreResponse)
async def get_volatility_score(
    asset: str,
    timeframe: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current volatility score for a specific asset/timeframe pair."""
    row = await repo.get_volatility_score(session, asset.upper(), timeframe)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No volatility score found for {asset}/{timeframe}",
        )
    return VolatilityScoreResponse.model_validate(row)
