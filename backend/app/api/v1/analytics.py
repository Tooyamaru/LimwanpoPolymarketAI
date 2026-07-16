"""
Analytics router — Layers 15 & 16.

GET /analytics/performance — full trading performance report (CLOSED positions only)
GET /analytics/capital     — capital management kill-switch status

Read-only.  No trade generation or modification.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.analytics import CapitalStatusResponse, PerformanceAnalyticsResponse
from app.services.capital_management_service import CapitalManagementService
from app.services.performance_analytics_service import PerformanceAnalyticsService

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_perf_service = PerformanceAnalyticsService()
_capital_service = CapitalManagementService()


@router.get("/performance", response_model=PerformanceAnalyticsResponse, response_model_by_alias=True)
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
    data = await _perf_service.get_performance_analytics(session)
    return PerformanceAnalyticsResponse(**data)


@router.get("/capital", response_model=CapitalStatusResponse, response_model_by_alias=True)
async def get_capital_status(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Capital management kill-switch status (Layer 16).

    Uses CLOSED positions only (realized_pnl as source of truth).
    Unrealized PnL is never used.

    Returns:
    - allowed: whether new trades may be opened
    - reason: kill-switch reason code if blocked, null otherwise
    - daily_pnl: today's realized PnL (UTC day boundary)
    - weekly_pnl: this week's realized PnL (Mon–Sun UTC)
    - consecutive_losses: count of consecutive losing closes from most recent
    - drawdown_percent: current equity curve peak-to-trough drawdown %

    CLOSE_POSITION decisions are always permitted regardless of this status.
    """
    status = await _capital_service.evaluate(session)
    return CapitalStatusResponse(
        allowed=status.allowed,
        reason=status.reason,
        daily_pnl=status.daily_pnl,
        weekly_pnl=status.weekly_pnl,
        consecutive_losses=status.consecutive_losses,
        drawdown_percent=status.drawdown_percent,
    )
