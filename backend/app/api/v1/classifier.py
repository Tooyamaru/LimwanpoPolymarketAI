"""
Classifier API — Sprint 4.

GET /api/v1/classifier           — all classified markets (full transparency)
GET /api/v1/classifier/updown    — UPDOWN markets only
GET /api/v1/classifier/stats     — aggregate classification statistics
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.discovery_run import DiscoveryRun
from app.repositories.event_classification_repository import get_classifications
from app.schemas.classifier import ClassificationResponse, ClassifierStatsResponse
from app.services.event_classifier import EventType

router = APIRouter(prefix="/classifier", tags=["classifier"])


@router.get(
    "",
    response_model=list[ClassificationResponse],
    summary="All classified markets with transparency metadata",
)
async def list_classifications(
    session: AsyncSession = Depends(get_db_session),
) -> list[ClassificationResponse]:
    rows = await get_classifications(session)
    return [ClassificationResponse.model_validate(r) for r in rows]


@router.get(
    "/updown",
    response_model=list[ClassificationResponse],
    summary="UPDOWN markets only — the scanner's active universe",
)
async def list_updown_markets(
    session: AsyncSession = Depends(get_db_session),
) -> list[ClassificationResponse]:
    rows = await get_classifications(session, event_type=EventType.UPDOWN.value)
    return [ClassificationResponse.model_validate(r) for r in rows]


@router.get(
    "/stats",
    response_model=ClassifierStatsResponse,
    summary="Aggregate classification statistics across all scanned markets",
)
async def classifier_stats(
    session: AsyncSession = Depends(get_db_session),
) -> ClassifierStatsResponse:
    """
    Returns classification counts from the latest discovery run.

    The totals cover ALL markets scanned (250k+), not just the asset+timeframe
    filtered subset.  These numbers are stored in discovery_runs after each scan.
    """
    result = await session.execute(
        select(DiscoveryRun).order_by(DiscoveryRun.run_at.desc()).limit(1)
    )
    run = result.scalar_one_or_none()

    if run is None:
        return ClassifierStatsResponse(
            total=0, updown=0, price_range=0,
            news_event=0, politics=0, other=0,
        )

    return ClassifierStatsResponse(
        total=run.total_scanned,
        updown=run.updown_count,
        price_range=run.price_range_count,
        news_event=run.news_event_count,
        politics=run.politics_count,
        other=run.other_count,
        run_at=run.run_at,
    )
