"""
Signals router — Layer 4: Signal Engine.

GET /signals/latest          — most recent N signals (all markets)
GET /signals/active          — signals from currently-active markets only
GET /signals/ranked          — signals sorted by confidence_score DESC (Phase 1)
GET /signals/stats           — count by type, severity, regime + avg confidence
GET /signals/{condition_id}  — signals for a specific market
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories import signal_repository as repo
from app.schemas.signal import RankedSignalResponse, SignalResponse, SignalStatsResponse

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


@router.get("/ranked", response_model=list[RankedSignalResponse])
async def get_ranked_signals(
    limit: int = Query(default=50, ge=1, le=200),
    min_confidence: float = Query(default=0.0, ge=0.0, le=100.0),
    asset: str = Query(default=None),
    mtf_only: bool = Query(default=False),
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Return signals ranked by confidence_score DESC.

    Query parameters
    ----------------
    limit            : max results (default 50, max 200)
    min_confidence   : only signals with confidence_score >= this value
    asset            : filter by asset symbol (BTC, ETH, SOL, XRP)
    mtf_only         : if true, only multi-timeframe-confirmed signals
    lookback_minutes : only signals from the last N minutes (default 60)
    """
    signals = await repo.get_ranked_signals(
        session,
        limit=limit,
        min_confidence=min_confidence,
        asset=asset,
        mtf_only=mtf_only,
        lookback_minutes=lookback_minutes,
    )
    return [
        RankedSignalResponse(
            rank=i + 1,
            id=s.id,
            condition_id=s.condition_id,
            asset=s.asset,
            timeframe=s.timeframe,
            signal_type=s.signal_type,
            severity=s.severity,
            confidence_score=s.confidence_score,
            regime=s.regime,
            mtf_confirmed=s.mtf_confirmed,
            yes_mid_after=s.yes_mid_after,
            yes_mid_delta=s.yes_mid_delta,
            seed_deviation=s.seed_deviation,
            spread_after=s.spread_after,
            detected_at=s.detected_at,
        )
        for i, s in enumerate(signals)
    ]


@router.get("/stats", response_model=SignalStatsResponse)
async def get_signal_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate statistics on stored signals."""
    total = await repo.get_signal_count(session)
    by_type = await repo.get_signal_counts_by_type(session)
    by_severity = await repo.get_signal_counts_by_severity(session)
    by_regime = await repo.get_signal_counts_by_regime(session)
    avg_confidence = await repo.get_average_confidence(session)
    mtf_count = await repo.get_mtf_confirmed_count(session)
    return SignalStatsResponse(
        total_signals=total,
        by_type=by_type,
        by_severity=by_severity,
        by_regime=by_regime,
        avg_confidence=avg_confidence,
        mtf_confirmed_count=mtf_count,
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
