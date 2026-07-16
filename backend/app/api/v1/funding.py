"""
Funding router — Funding Engine (Phase Next, supporting engine).

GET /funding          — current funding reading for every scored asset
GET /funding/{asset}  — single asset detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import funding_repository as repo
from app.schemas.funding import FundingScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/funding", tags=["decision-engine"])


@router.get("", response_model=list[FundingScoreResponse])
async def get_all_funding_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current funding reading for every scored asset."""
    rows = await repo.get_all_funding_scores(session)
    return [FundingScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}", response_model=FundingScoreResponse)
async def get_funding_score(
    asset: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current funding reading for a specific asset."""
    row = await repo.get_funding_score(session, asset.upper())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No funding score found for asset={asset}",
        )
    return FundingScoreResponse.model_validate(row)
