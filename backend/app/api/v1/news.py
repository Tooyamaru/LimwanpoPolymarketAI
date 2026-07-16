"""
News router — News Engine (Phase Next, supporting engine — DEFERRED stub).

GET /news          — current (always-neutral) sentiment reading for every asset
GET /news/{asset}  — single asset detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import news_repository as repo
from app.schemas.news import NewsScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/news", tags=["decision-engine"])


@router.get("", response_model=list[NewsScoreResponse])
async def get_all_news_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current (deferred/stub) sentiment reading for every asset."""
    rows = await repo.get_all_news_scores(session)
    return [NewsScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}", response_model=NewsScoreResponse)
async def get_news_score(
    asset: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current (deferred/stub) sentiment reading for a specific asset."""
    row = await repo.get_news_score(session, asset.upper())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No news score found for asset={asset}",
        )
    return NewsScoreResponse.model_validate(row)
