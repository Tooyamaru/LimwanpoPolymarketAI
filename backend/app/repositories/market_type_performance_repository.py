"""market_type_performance_repository.py — Priority 5 persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_type_performance import MarketTypePerformance

logger = get_logger(__name__)


async def upsert_market_type_performance(
    session: AsyncSession,
    *,
    asset: str,
    timeframe: str,
    market_type: str,
    total_trades: int,
    wins: int,
    losses: int,
    win_rate: Optional[float],
    accuracy: Optional[float],
    avg_pnl: Optional[float],
    max_drawdown: Optional[float],
    avg_confidence: Optional[float],
) -> MarketTypePerformance:
    stmt = (
        pg_insert(MarketTypePerformance)
        .values(
            asset=asset,
            timeframe=timeframe,
            market_type=market_type,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            accuracy=accuracy,
            avg_pnl=avg_pnl,
            max_drawdown=max_drawdown,
            avg_confidence=avg_confidence,
            computed_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["asset", "timeframe", "market_type"],
            set_={
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "accuracy": accuracy,
                "avg_pnl": avg_pnl,
                "max_drawdown": max_drawdown,
                "avg_confidence": avg_confidence,
                "computed_at": datetime.now(timezone.utc),
            },
        )
        .returning(MarketTypePerformance)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all(session: AsyncSession) -> list[MarketTypePerformance]:
    result = await session.execute(
        select(MarketTypePerformance).order_by(MarketTypePerformance.accuracy.desc().nulls_last())
    )
    return list(result.scalars().all())


async def get_by_asset_timeframe(
    session: AsyncSession, asset: str, timeframe: str
) -> list[MarketTypePerformance]:
    result = await session.execute(
        select(MarketTypePerformance).where(
            MarketTypePerformance.asset == asset,
            MarketTypePerformance.timeframe == timeframe,
        )
    )
    return list(result.scalars().all())
