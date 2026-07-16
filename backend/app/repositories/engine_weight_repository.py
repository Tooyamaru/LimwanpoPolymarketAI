"""engine_weight_repository.py — Dynamic engine weight persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.engine_weight import BASE_WEIGHTS, WEIGHT_MAX, WEIGHT_MIN, EngineWeight

logger = get_logger(__name__)


async def upsert_engine_weight(
    session: AsyncSession,
    *,
    engine_name: str,
    current_weight: float,
    adjustment_factor: Optional[float] = None,
    outcomes_evaluated: int = 0,
    accuracy_at_adjustment: Optional[float] = None,
    recency_accuracy: Optional[float] = None,
    stability_score: Optional[float] = None,
    factor_breakdown: Optional[str] = None,
) -> EngineWeight:
    base = BASE_WEIGHTS.get(engine_name, current_weight)
    w_min = WEIGHT_MIN.get(engine_name, 0.01)
    w_max = WEIGHT_MAX.get(engine_name, 1.0)

    stmt = (
        pg_insert(EngineWeight)
        .values(
            engine_name=engine_name,
            base_weight=base,
            current_weight=current_weight,
            min_weight=w_min,
            max_weight=w_max,
            adjustment_factor=adjustment_factor,
            outcomes_evaluated=outcomes_evaluated,
            accuracy_at_adjustment=accuracy_at_adjustment,
            recency_accuracy=recency_accuracy,
            stability_score=stability_score,
            factor_breakdown=factor_breakdown,
            last_adjusted_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["engine_name"],
            set_={
                "current_weight": current_weight,
                "adjustment_factor": adjustment_factor,
                "outcomes_evaluated": outcomes_evaluated,
                "accuracy_at_adjustment": accuracy_at_adjustment,
                "recency_accuracy": recency_accuracy,
                "stability_score": stability_score,
                "factor_breakdown": factor_breakdown,
                "last_adjusted_at": datetime.now(timezone.utc),
            },
        )
        .returning(EngineWeight)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all_engine_weights(session: AsyncSession) -> list[EngineWeight]:
    result = await session.execute(select(EngineWeight))
    return list(result.scalars().all())


async def get_effective_weights(session: AsyncSession) -> dict[str, float]:
    """
    Return current effective weights for all directional voting engines.
    Falls back to BASE_WEIGHTS if no DB records exist (safe cold-start).
    """
    rows = await get_all_engine_weights(session)
    weights = dict(BASE_WEIGHTS)  # start with defaults
    for row in rows:
        weights[row.engine_name] = row.current_weight
    return weights


async def get_engine_weight(
    session: AsyncSession, engine_name: str
) -> Optional[EngineWeight]:
    result = await session.execute(
        select(EngineWeight).where(EngineWeight.engine_name == engine_name)
    )
    return result.scalar_one_or_none()
