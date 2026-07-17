"""
Risk router — Layer 9: Risk Engine.

GET /risk                 — recent risk evaluation events (ALLOW + BLOCK)
GET /risk/blocked         — BLOCKED decisions only
GET /risk/stats           — aggregate counts and block rate
GET /risk/capital-status  — one-stop capital management status (Layer 16)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import risk_repository as repo
from app.schemas.risk import (
    CapitalStatusDetailedResponse,
    RiskEventResponse,
    RiskStatsResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("", response_model=list[RiskEventResponse])
async def get_risk_events(
    result: str | None = Query(
        default=None,
        description="Filter by result: ALLOW | BLOCK",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return recent risk evaluation events, newest first."""
    rows = await repo.get_risk_events(session, result_filter=result, limit=limit)
    return [RiskEventResponse.model_validate(r) for r in rows]


@router.get("/blocked", response_model=list[RiskEventResponse])
async def get_blocked_events(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return BLOCKED risk events only, newest first."""
    rows = await repo.get_blocked_events(session, limit=limit)
    return [RiskEventResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=RiskStatsResponse)
async def get_risk_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate risk evaluation counts and block rate."""
    stats = await repo.get_risk_stats(session)
    return RiskStatsResponse(**stats)


@router.get("/capital-status", response_model=CapitalStatusDetailedResponse)
async def get_capital_status(
    session: AsyncSession = Depends(get_db_session),
):
    """
    One-stop capital management status — single source of truth for the
    frontend header and any external consumer.

    Covers all Layer-16 kill-switch rules (DAILY_LOSS_LIMIT,
    WEEKLY_LOSS_LIMIT, LOSS_STREAK_LIMIT, MAX_DRAWDOWN_LIMIT) and exposes
    the full equity/drawdown picture so the reason for any block is
    unambiguous.

    Equity formula: current_equity = initial_capital + realized_pnl + unrealized_pnl
    Drawdown formula: (peak_equity - current_equity) / peak_equity × 100
    Peak is anchored to initial_capital (never below it).
    """
    from app.services.capital_management_service import CapitalManagementService

    svc = CapitalManagementService()
    detail = await svc.evaluate_detailed(session)

    return CapitalStatusDetailedResponse(
        capital_blocked=detail.capital_blocked,
        block_code=detail.block_code,
        block_reason=detail.block_reason,
        block_scope=detail.block_scope,
        blocked_at=detail.blocked_at,
        blocked_until=detail.blocked_until,
        reset_policy=detail.reset_policy,
        reset_available=detail.reset_available,
        initial_capital=detail.initial_capital,
        current_equity=detail.current_equity,
        peak_equity=detail.peak_equity,
        drawdown_amount=detail.drawdown_amount,
        drawdown_percent=detail.drawdown_percent,
        max_drawdown_limit=detail.max_drawdown_limit,
        daily_start_equity=detail.daily_start_equity,
        daily_loss_amount=detail.daily_loss_amount,
        daily_drawdown_percent=detail.daily_drawdown_percent,
        daily_loss_limit=detail.daily_loss_limit,
        consecutive_losses=detail.consecutive_losses,
        consecutive_loss_limit=detail.consecutive_loss_limit,
        open_exposure=detail.open_exposure,
        available_capital=detail.available_capital,
        daily_pnl=detail.daily_pnl,
        weekly_pnl=detail.weekly_pnl,
        data_source=detail.data_source,
        last_updated_at=detail.last_updated_at,
    )
