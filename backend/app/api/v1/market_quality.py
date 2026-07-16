"""
Market Quality router — Polymarket Market Engine (Phase Next, PRIMARY gate).

GET /market-quality                  — current quality score for every scored market
GET /market-quality/{condition_id}   — single market detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import market_quality_repository as repo
from app.schemas.market_quality import MarketQualityResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/market-quality", tags=["decision-engine"])


@router.get("", response_model=list[MarketQualityResponse])
async def get_all_market_quality_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current market quality score for every scored market."""
    rows = await repo.get_all_market_quality_scores(session)
    return [MarketQualityResponse.model_validate(r) for r in rows]


@router.get("/{condition_id}", response_model=MarketQualityResponse)
async def get_market_quality_score(
    condition_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current market quality score for a specific market."""
    row = await repo.get_market_quality_score(session, condition_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No market quality score found for condition_id={condition_id}",
        )
    return MarketQualityResponse.model_validate(row)
