"""
Feed Service — Phase 5: Source Stabilization.

Assembles the real AI Activity feed from engine-written rows.
Read-only: delegates all DB reads to feed_repository.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import feed_repository as repo

logger = get_logger(__name__)


class FeedService:
    async def get_recent_events(self, session: AsyncSession, limit: int = 8) -> list[dict]:
        events = await repo.get_recent_events(session, limit=limit)
        logger.debug("Feed events assembled", count=len(events))
        return events
