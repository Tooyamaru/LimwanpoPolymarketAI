"""
Signal repository — Layer 4: Signal Engine.

All DB persistence and query operations for the `signals` table.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.signal import Signal

logger = get_logger(__name__)


async def save_signal(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    signal_type: str,
    yes_mid_before: Optional[float] = None,
    yes_mid_after: Optional[float] = None,
    yes_mid_delta: Optional[float] = None,
    spread_before: Optional[float] = None,
    spread_after: Optional[float] = None,
    spread_delta: Optional[float] = None,
    seed_deviation: Optional[float] = None,
    severity: str = "LOW",
    confidence_score: Optional[float] = None,
    regime: Optional[str] = None,
    mtf_confirmed: Optional[bool] = False,
    snapshot_id_before: Optional[int] = None,
    snapshot_id_after: Optional[int] = None,
    detected_at: Optional[datetime] = None,
) -> Signal:
    """Insert a new signal row and return it."""
    if detected_at is None:
        detected_at = datetime.now(timezone.utc)

    signal = Signal(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        signal_type=signal_type,
        yes_mid_before=yes_mid_before,
        yes_mid_after=yes_mid_after,
        yes_mid_delta=yes_mid_delta,
        spread_before=spread_before,
        spread_after=spread_after,
        spread_delta=spread_delta,
        seed_deviation=seed_deviation,
        severity=severity,
        confidence_score=confidence_score,
        regime=regime,
        mtf_confirmed=mtf_confirmed,
        snapshot_id_before=snapshot_id_before,
        snapshot_id_after=snapshot_id_after,
        detected_at=detected_at,
    )
    session.add(signal)
    await session.flush()

    logger.info(
        "Signal detected",
        signal_type=signal_type,
        asset=asset,
        timeframe=timeframe,
        severity=severity,
        confidence_score=confidence_score,
        regime=regime,
        mtf_confirmed=mtf_confirmed,
        yes_mid_before=yes_mid_before,
        yes_mid_after=yes_mid_after,
        delta=yes_mid_delta,
    )
    return signal


async def get_latest_signals(
    session: AsyncSession,
    limit: int = 50,
) -> list[Signal]:
    """Return the most recent `limit` signals across all markets."""
    result = await session.execute(
        select(Signal)
        .order_by(desc(Signal.detected_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_signals_by_market(
    session: AsyncSession,
    condition_id: str,
    limit: int = 20,
) -> list[Signal]:
    """Return the latest `limit` signals for a specific condition_id."""
    result = await session.execute(
        select(Signal)
        .where(Signal.condition_id == condition_id)
        .order_by(desc(Signal.detected_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_active_market_signals(
    session: AsyncSession,
    limit: int = 50,
) -> list[Signal]:
    """Return recent signals only for currently-active universe markets."""
    active_ids_stmt = (
        select(MarketUniverse.condition_id)
        .where(MarketUniverse.status == "active")
    )
    active_ids_result = await session.execute(active_ids_stmt)
    active_condition_ids = [r[0] for r in active_ids_result.all()]

    if not active_condition_ids:
        return []

    result = await session.execute(
        select(Signal)
        .where(Signal.condition_id.in_(active_condition_ids))
        .order_by(desc(Signal.detected_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_ranked_signals(
    session: AsyncSession,
    limit: int = 50,
    min_confidence: float = 0.0,
    asset: Optional[str] = None,
    mtf_only: bool = False,
    lookback_minutes: int = 60,
) -> list[Signal]:
    """
    Return signals ranked by confidence_score DESC, then detected_at DESC.

    Parameters
    ----------
    limit            : max rows returned
    min_confidence   : only return signals with confidence_score >= this value
    asset            : filter by asset (BTC, ETH, SOL, XRP)
    mtf_only         : if True, only return MTF-confirmed signals
    lookback_minutes : only signals from the last N minutes
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    stmt = (
        select(Signal)
        .where(Signal.detected_at >= cutoff)
    )

    if min_confidence > 0:
        stmt = stmt.where(Signal.confidence_score >= min_confidence)

    if asset:
        stmt = stmt.where(Signal.asset == asset)

    if mtf_only:
        stmt = stmt.where(Signal.mtf_confirmed.is_(True))

    stmt = (
        stmt
        .order_by(desc(Signal.confidence_score), desc(Signal.detected_at))
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_recent_signals_by_asset(
    session: AsyncSession,
    asset: str,
    lookback_seconds: int = 300,
) -> list[Signal]:
    """
    Return signals for a given asset within the last `lookback_seconds`.

    Used by the signal engine to compute multi-timeframe confirmation.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lookback_seconds)
    result = await session.execute(
        select(Signal)
        .where(
            Signal.asset == asset,
            Signal.detected_at >= cutoff,
        )
        .order_by(desc(Signal.detected_at))
    )
    return list(result.scalars().all())


async def get_signal_count(session: AsyncSession) -> int:
    """Return total number of signals stored."""
    result = await session.execute(select(func.count()).select_from(Signal))
    return result.scalar_one()


async def get_signal_counts_by_type(session: AsyncSession) -> dict[str, int]:
    """Return signal count per signal_type."""
    result = await session.execute(
        select(Signal.signal_type, func.count(Signal.id).label("cnt"))
        .group_by(Signal.signal_type)
        .order_by(desc("cnt"))
    )
    return {row[0]: row[1] for row in result.all()}


async def get_signal_counts_by_severity(session: AsyncSession) -> dict[str, int]:
    """Return signal count per severity."""
    result = await session.execute(
        select(Signal.severity, func.count(Signal.id).label("cnt"))
        .group_by(Signal.severity)
        .order_by(desc("cnt"))
    )
    return {row[0]: row[1] for row in result.all()}


async def get_signal_counts_by_regime(session: AsyncSession) -> dict[str, int]:
    """Return signal count per regime."""
    result = await session.execute(
        select(Signal.regime, func.count(Signal.id).label("cnt"))
        .where(Signal.regime.isnot(None))
        .group_by(Signal.regime)
        .order_by(desc("cnt"))
    )
    return {row[0]: row[1] for row in result.all()}


async def get_average_confidence(session: AsyncSession) -> Optional[float]:
    """Return average confidence_score across all signals that have one."""
    result = await session.execute(
        select(func.avg(Signal.confidence_score))
        .where(Signal.confidence_score.isnot(None))
    )
    val = result.scalar_one_or_none()
    return round(float(val), 2) if val is not None else None


async def get_mtf_confirmed_count(session: AsyncSession) -> int:
    """Return count of signals with mtf_confirmed = True."""
    result = await session.execute(
        select(func.count())
        .select_from(Signal)
        .where(Signal.mtf_confirmed.is_(True))
    )
    return result.scalar_one()


async def get_last_signal_for_market(
    session: AsyncSession,
    condition_id: str,
    signal_type: str,
) -> Optional[Signal]:
    """Return the most recent signal of given type for a market."""
    result = await session.execute(
        select(Signal)
        .where(
            Signal.condition_id == condition_id,
            Signal.signal_type == signal_type,
        )
        .order_by(desc(Signal.detected_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
