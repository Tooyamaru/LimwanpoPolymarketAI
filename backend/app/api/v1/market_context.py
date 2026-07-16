"""
Market Context router — Market Context Engine (Phase Next).

GET /market-context          — current context status for every scored asset
GET /market-context/{asset}  — single asset detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import market_context_repository as repo
from app.schemas.market_context import MarketContextResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/market-context", tags=["decision-engine"])


@router.get("", response_model=list[MarketContextResponse])
async def get_all_market_context_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current market context status for every scored asset."""
    rows = await repo.get_all_market_context_scores(session)
    return [MarketContextResponse.model_validate(r) for r in rows]


@router.get("/{asset}", response_model=MarketContextResponse)
async def get_market_context_score(
    asset: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current market context status for a specific asset."""
    row = await repo.get_market_context_score(session, asset.upper())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No market context score found for asset={asset}",
        )
    return MarketContextResponse.model_validate(row)
