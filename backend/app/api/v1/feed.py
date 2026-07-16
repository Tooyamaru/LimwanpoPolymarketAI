"""
Feed router — Phase 5: Source Stabilization.

GET /feed/recent — real, chronological AI Activity feed.

Every event traces to an actual Signal / RiskEvent / DecisionLog row
written by an engine. No fabricated, random, or hardcoded messages.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.feed import FeedEventResponse
from app.services.feed_service import FeedService

logger = get_logger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])

_service = FeedService()


@router.get("/recent", response_model=list[FeedEventResponse])
async def get_recent_feed(
    limit: int = Query(default=8, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
):
    """Real, chronological AI Activity feed — sourced only from engine-written rows."""
    data = await _service.get_recent_events(session, limit=limit)
    return [FeedEventResponse(**e) for e in data]
