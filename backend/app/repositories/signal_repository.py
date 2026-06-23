"""
Signal repository — Layer 4: Signal Engine.

All DB persistence and query operations for the `signals` table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.signal import Signal
from app.models.market_universe import MarketUniverse

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
