"""
Signals router — Layer 4: Signal Engine.

GET /signals/latest          — most recent N signals (all markets)
GET /signals/active          — signals from currently-active markets only
GET /signals/stats           — count by type and severity
GET /signals/{condition_id}  — signals for a specific market
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import signal_repository as repo
from app.schemas.signal import SignalResponse, SignalStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/latest", response_model=list[SignalResponse])
async def get_latest_signals(
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the most recent `limit` signals across all markets."""
    signals = await repo.get_latest_signals(session, limit=limit)
    return [SignalResponse.model_validate(s) for s in signals]


@router.get("/active", response_model=list[SignalResponse])
async def get_active_market_signals(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """Return recent signals for currently-active universe markets only."""
    signals = await repo.get_active_market_signals(session, limit=limit)
    return [SignalResponse.model_validate(s) for s in signals]


@router.get("/stats", response_model=SignalStatsResponse)
async def get_signal_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate statistics on stored signals."""
    total = await repo.get_signal_count(session)
    by_type = await repo.get_signal_counts_by_type(session)
    by_severity = await repo.get_signal_counts_by_severity(session)
    return SignalStatsResponse(
        total_signals=total,
        by_type=by_type,
        by_severity=by_severity,
    )


@router.get("/{condition_id}", response_model=list[SignalResponse])
async def get_signals_by_market(
    condition_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the latest `limit` signals for a specific condition_id."""
    signals = await repo.get_signals_by_market(session, condition_id, limit=limit)
    if not signals:
        raise HTTPException(
            status_code=404,
            detail=f"No signals found for condition_id={condition_id}",
        )
    return [SignalResponse.model_validate(s) for s in signals]
