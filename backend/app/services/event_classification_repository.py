"""
Event classification repository — Sprint 4.

Persistence layer for the event_classifications table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.event_classification import EventClassification
from app.services.event_classifier import EventType

logger = get_logger(__name__)


async def save_classification(
    session: AsyncSession,
    *,
    market_id: str,
    raw_title: str,
    event_type: str,
    confidence: float,
    matched_rule: str,
    created_at: Optional[datetime] = None,
) -> EventClassification:
    """
    Upsert an event classification.

    If the market_id already exists we update event_type / confidence / matched_rule
    in case the classification rules have improved.
    """
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    stmt = select(EventClassification).where(EventClassification.market_id == market_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.event_type = event_type
        existing.confidence = confidence
        existing.matched_rule = matched_rule
        existing.raw_title = raw_title
        return existing

    row = EventClassification(
        market_id=market_id,
        raw_title=raw_title,
        event_type=event_type,
        confidence=confidence,
        matched_rule=matched_rule,
        created_at=created_at,
    )
    session.add(row)
    await session.flush()
    logger.debug(
        "New event classification inserted",
        market_id=market_id,
        event_type=event_type,
        confidence=confidence,
    )
    return row


async def get_classifications(
    session: AsyncSession,
    event_type: Optional[str] = None,
) -> list[EventClassification]:
    """Return event classifications, optionally filtered by event_type."""
    stmt = select(EventClassification).order_by(
        EventClassification.event_type, EventClassification.created_at
    )
    if event_type is not None:
        stmt = stmt.where(EventClassification.event_type == event_type)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_classification_db_stats(session: AsyncSession) -> dict:
    """
    Aggregate counts from the event_classifications table.

    These counts only cover matched markets (asset+timeframe filtered), NOT
    the full 250k scan.  Full-scan stats come from discovery_runs.
    """
    stmt = select(
        func.count().label("total"),
        func.sum(
            case((EventClassification.event_type == EventType.UPDOWN.value, 1), else_=0)
        ).label("updown"),
        func.sum(
            case((EventClassification.event_type == EventType.PRICE_RANGE.value, 1), else_=0)
        ).label("price_range"),
        func.sum(
            case((EventClassification.event_type == EventType.NEWS_EVENT.value, 1), else_=0)
        ).label("news_event"),
        func.sum(
            case((EventClassification.event_type == EventType.POLITICS.value, 1), else_=0)
        ).label("politics"),
        func.sum(
            case((EventClassification.event_type == EventType.OTHER.value, 1), else_=0)
        ).label("other"),
    )
    result = await session.execute(stmt)
    row = result.one()
    return {
        "total": int(row.total or 0),
        "updown": int(row.updown or 0),
        "price_range": int(row.price_range or 0),
        "news_event": int(row.news_event or 0),
        "politics": int(row.politics or 0),
        "other": int(row.other or 0),
    }
