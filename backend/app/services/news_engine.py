"""
News Engine — Phase Next, supporting engine — DEFERRED (stub).

Per the Decision Engine Evolution brief, the news/sentiment engine is
explicitly deferred: no external news or sentiment data source is wired up
in this phase. This engine always reports NEUTRAL with confidence 0 so the
Decision Engine can already read a News row from day one and light up
automatically once a real news feed is connected later — no Decision Engine
changes will be required at that point.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import news_repository as repo
from app.repositories.universe_repository import get_active_universe

logger = get_logger(__name__)

DEFERRED_REASON = (
    "News engine deferred — no external news/sentiment data source configured "
    "for this phase. Always reports NEUTRAL with zero confidence."
)


class NewsEngine:
    """
    Usage (from a background loop)::

        engine = NewsEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        universe = await get_active_universe(session)
        assets = sorted({m.asset for m in universe})

        for asset in assets:
            await repo.upsert_news_score(
                session,
                asset=asset,
                sentiment="NEUTRAL",
                confidence=0.0,
                reason=DEFERRED_REASON,
            )

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "News engine cycle complete (stub — deferred)",
            assets=len(assets),
            duration_ms=elapsed_ms,
        )
        return {"assets": len(assets), "scored": len(assets), "skipped": 0, "errors": 0}
