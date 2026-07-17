"""
Portfolio router — Layer 10: Portfolio Reporting.

GET /portfolio/summary   — high-level portfolio snapshot
GET /portfolio/positions — position breakdown by status / asset / side
GET /portfolio/orders    — order breakdown by status / asset / side
GET /portfolio/risk      — risk check counts and block reasons
GET /portfolio/pnl       — unrealized and realized PnL aggregates

All endpoints are read-only. No trade generation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services.portfolio_service import PortfolioService
from app.schemas.portfolio import (
    AccountingResponse,
    OrderSummaryResponse,
    PnlSummaryResponse,
    PortfolioSummaryResponse,
    PositionSummaryResponse,
    RiskSummaryResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_service = PortfolioService()


@router.get("/accounting", response_model=AccountingResponse)
async def get_accounting(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Global accounting snapshot — spec §9 source of truth for dashboard financial widgets.

    portfolio_active_lots      = COUNT positions WHERE status IN ('OPEN', 'PARTIAL')
    open_exposure              = SUM(remaining_quantity × entry_price) for active lots
    raw_available_capital      = initial_capital + total_realized_pnl - open_exposure
    spendable_available_capital = max(0, raw_available_capital)
    cumulative_outcome          = total_realized_pnl + total_unrealized_pnl
    """
    data = await _service.get_accounting_summary(session)
    return AccountingResponse(**data)


@router.get("/summary", response_model=PortfolioSummaryResponse, response_model_by_alias=True)
async def get_portfolio_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    High-level portfolio snapshot.

    Returns position counts (total/open/closed), order counts,
    and trade-decision approval/block totals.
    """
    data = await _service.get_portfolio_summary(session)
    return PortfolioSummaryResponse(**data)


@router.get("/positions", response_model=PositionSummaryResponse, response_model_by_alias=True)
async def get_position_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Position breakdown by status, asset, and side.
    """
    data = await _service.get_position_summary(session)
    return PositionSummaryResponse(**data)


@router.get("/orders", response_model=OrderSummaryResponse)
async def get_order_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Order breakdown by status, asset, and side.
    """
    data = await _service.get_order_summary(session)
    return OrderSummaryResponse(**data)


@router.get("/risk", response_model=RiskSummaryResponse)
async def get_risk_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Risk check statistics: allowed/blocked counts and block-reason breakdown.
    """
    data = await _service.get_risk_summary(session)
    return RiskSummaryResponse(**data)


@router.get("/pnl", response_model=PnlSummaryResponse, response_model_by_alias=True)
async def get_pnl_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    PnL aggregates: unrealized from OPEN positions, realized from CLOSED positions.
    """
    data = await _service.get_pnl_summary(session)
    return PnlSummaryResponse(**data)
