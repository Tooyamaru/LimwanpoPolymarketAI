"""
Orderbook repository — Orderbook Engine (Phase Next, supporting engine).

UPSERT by asset, mirroring momentum_repository.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.orderbook_score import OrderbookScore

logger = get_logger(__name__)


async def upsert_orderbook_score(
    session: AsyncSession,
    *,
    asset: str,
    direction: str,
    confidence: float,
    reason: Optional[str],
    bid_volume: Optional[float],
    ask_volume: Optional[float],
    imbalance_pct: Optional[float],
    computed_at: Optional[datetime] = None,
) -> None:
    if computed_at is None:
        computed_at = datetime.now(timezone.utc)

    values = {
        "asset": asset,
        "direction": direction,
        "confidence": round(confidence, 2),
        "reason": reason,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "imbalance_pct": imbalance_pct,
        "computed_at": computed_at,
    }
    update_values = {k: v for k, v in values.items() if k != "asset"}

    stmt = (
        pg_insert(OrderbookScore)
        .values(**values)
        .on_conflict_do_update(index_elements=["asset"], set_=update_values)
    )
    await session.execute(stmt)

    logger.debug("Orderbook score upserted", asset=asset, direction=direction)


async def get_orderbook_score(session: AsyncSession, asset: str) -> Optional[OrderbookScore]:
    result = await session.execute(
        select(OrderbookScore).where(OrderbookScore.asset == asset)
    )
    return result.scalar_one_or_none()


async def get_all_orderbook_scores(session: AsyncSession) -> list[OrderbookScore]:
    result = await session.execute(select(OrderbookScore))
    return list(result.scalars().all())
