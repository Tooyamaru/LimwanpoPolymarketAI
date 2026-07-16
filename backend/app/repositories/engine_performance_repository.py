"""engine_performance_repository.py — Engine performance statistics persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.engine_performance import EnginePerformance

logger = get_logger(__name__)

_GRADE_THRESHOLDS = [("A", 80.0), ("B", 65.0), ("C", 50.0), ("D", 35.0), ("F", 0.0)]

TRACKED_ENGINES = [
    "opportunity", "orderbook", "momentum", "trend",
    "funding", "market_context", "market_quality",
]


def _grade(accuracy: Optional[float]) -> Optional[str]:
    if accuracy is None:
        return None
    for letter, threshold in _GRADE_THRESHOLDS:
        if accuracy >= threshold:
            return letter
    return "F"


async def upsert_engine_performance(
    session: AsyncSession,
    *,
    engine_name: str,
    wins: int,
    losses: int,
    abstentions: int,
    total_evaluated: int,
    accuracy: Optional[float],
    avg_confidence_when_correct: Optional[float] = None,
    avg_confidence_when_wrong: Optional[float] = None,
    contribution_score: Optional[float] = None,
    contribution_pct: Optional[float] = None,
) -> EnginePerformance:
    grade = _grade(accuracy)
    stmt = (
        pg_insert(EnginePerformance)
        .values(
            engine_name=engine_name,
            wins=wins,
            losses=losses,
            abstentions=abstentions,
            total_evaluated=total_evaluated,
            accuracy=accuracy,
            avg_confidence_when_correct=avg_confidence_when_correct,
            avg_confidence_when_wrong=avg_confidence_when_wrong,
            contribution_score=contribution_score,
            contribution_pct=contribution_pct,
            grade=grade,
            last_updated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["engine_name"],
            set_={
                "wins": wins,
                "losses": losses,
                "abstentions": abstentions,
                "total_evaluated": total_evaluated,
                "accuracy": accuracy,
                "avg_confidence_when_correct": avg_confidence_when_correct,
                "avg_confidence_when_wrong": avg_confidence_when_wrong,
                "contribution_score": contribution_score,
                "contribution_pct": contribution_pct,
                "grade": grade,
                "last_updated_at": datetime.now(timezone.utc),
            },
        )
        .returning(EnginePerformance)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all_engine_performances(
    session: AsyncSession,
) -> list[EnginePerformance]:
    result = await session.execute(
        select(EnginePerformance).order_by(EnginePerformance.accuracy.desc().nulls_last())
    )
    return list(result.scalars().all())


async def get_engine_performance(
    session: AsyncSession, engine_name: str
) -> Optional[EnginePerformance]:
    result = await session.execute(
        select(EnginePerformance).where(EnginePerformance.engine_name == engine_name)
    )
    return result.scalar_one_or_none()
