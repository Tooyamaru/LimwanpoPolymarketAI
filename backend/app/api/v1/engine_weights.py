"""API — Dynamic Engine Weights (Priority 3)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import engine_weight_repository as ew_repo
from app.schemas.engine_weight import EngineWeightResponse, EngineWeightSummaryResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/engine-weights", tags=["engine-weights"])


@router.get("", response_model=EngineWeightSummaryResponse)
async def get_engine_weights(
    session: AsyncSession = Depends(get_db_session),
):
    """Current effective engine weights (dynamic vs base)."""
    rows = await ew_repo.get_all_engine_weights(session)

    adjusted = sum(
        1 for r in rows if r.adjustment_factor and abs(r.adjustment_factor) > 0.001
    )
    at_base = len(rows) - adjusted

    return EngineWeightSummaryResponse(
        total_engines=len(rows),
        engines_adjusted=adjusted,
        engines_at_base=at_base,
        engines=rows,
    )


@router.get("/effective", response_model=dict)
async def get_effective_weights(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the effective weight dict used by the Decision Engine."""
    return await ew_repo.get_effective_weights(session)
