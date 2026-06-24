"""
Analytics router — Layer 15: Performance Analytics.

GET /analytics/performance — full trading performance report (CLOSED positions only)

Read-only.  No trade generation or modification.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.analytics import PerformanceAnalyticsResponse
from app.services.performance_analytics_service import PerformanceAnalyticsService

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_service = PerformanceAnalyticsService()


@router.get("/performance", response_model=PerformanceAnalyticsResponse)
async def get_performance_analytics(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Full trading performance report.

    Uses CLOSED positions only (realized_pnl as source of truth).

    Returns trade counts, win rate, gross/net PnL, profit factor,
    expectancy, max drawdown, and per-asset / per-timeframe breakdowns.
    All metrics are 0 / null when no closed positions exist yet.
    """
    data = await _service.get_performance_analytics(session)
    return PerformanceAnalyticsResponse(**data)
