"""
Orderbook router — Orderbook Engine (Phase Next, supporting engine).

GET /orderbook          — current orderbook reading for every scored asset
GET /orderbook/{asset}  — single asset detail
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import orderbook_repository as repo
from app.schemas.orderbook import OrderbookScoreResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/orderbook", tags=["decision-engine"])


@router.get("", response_model=list[OrderbookScoreResponse])
async def get_all_orderbook_scores(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current orderbook reading for every scored asset."""
    rows = await repo.get_all_orderbook_scores(session)
    return [OrderbookScoreResponse.model_validate(r) for r in rows]


@router.get("/{asset}", response_model=OrderbookScoreResponse)
async def get_orderbook_score(
    asset: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current orderbook reading for a specific asset."""
    row = await repo.get_orderbook_score(session, asset.upper())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No orderbook score found for asset={asset}",
        )
    return OrderbookScoreResponse.model_validate(row)
