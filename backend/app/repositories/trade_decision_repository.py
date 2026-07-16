"""
Trade decision repository — Layer 6: Strategy Engine.

All DB persistence and query operations for the `trade_decisions` table.
Decisions are append-only — no UPSERTs.  Every engine cycle that produces
a OPEN_LONG_YES / OPEN_LONG_NO / WATCH decision writes a new row so the
full history is preserved.

SKIP decisions are NOT persisted by default (controlled by the engine's
STRATEGY_PERSIST_SKIPS setting) to keep the table lean.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.trade_decision import TradeDecision

logger = get_logger(__name__)


async def insert_decision(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    decision: str,
    opportunity_score: float,
    direction: str,
    yes_mid: Optional[float],
    yes_bid: Optional[float],
    yes_ask: Optional[float],
    spread_yes: Optional[float],
    skip_reason: Optional[str] = None,
    position_size_usdc: Optional[float] = None,
    status: str = "PENDING",
    decided_at: Optional[datetime] = None,
) -> TradeDecision:
    """Append a new trade decision row and return the persisted object."""
    if decided_at is None:
        decided_at = datetime.now(timezone.utc)

    row = TradeDecision(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        decision=decision,
        status=status,
        opportunity_score=round(opportunity_score, 2),
        direction=direction,
        yes_mid=yes_mid,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        spread_yes=spread_yes,
        skip_reason=skip_reason,
        position_size_usdc=position_size_usdc,
        decided_at=decided_at,
    )
    session.add(row)

    logger.debug(
        "Trade decision inserted",
        asset=asset,
        timeframe=timeframe,
        decision=decision,
        score=round(opportunity_score, 1),
        skip_reason=skip_reason,
        position_size_usdc=position_size_usdc,
    )
    return row


async def get_all_decisions(
    session: AsyncSession,
    decision_filter: Optional[str] = None,
    limit: int = 200,
) -> list[TradeDecision]:
    """Return recent decisions, newest first. Optionally filter by decision type."""
    stmt = select(TradeDecision)
    if decision_filter:
        stmt = stmt.where(TradeDecision.decision == decision_filter)
    stmt = stmt.order_by(desc(TradeDecision.decided_at)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_decisions(
    session: AsyncSession,
    limit: int = 100,
) -> list[TradeDecision]:
    """Return OPEN_LONG_YES / OPEN_LONG_NO decisions with status PENDING."""
    stmt = (
        select(TradeDecision)
        .where(
            TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
            TradeDecision.status == "PENDING",
        )
        .order_by(desc(TradeDecision.opportunity_score))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_previous_entry_decisions(
    session: AsyncSession,
    condition_ids: list[str],
) -> dict[str, TradeDecision]:
    """
    Return the most recent RISK_APPROVED or EXECUTED entry decision per
    condition_id for the given set of condition_ids.

    Used by the Risk Engine's SCALE_IN_NO_IMPROVEMENT gate: a second+ entry
    on the same condition_id is only allowed when it shows measurable
    improvement over the previous confirmed entry.

    Guarantees:
      - Only RISK_APPROVED / EXECUTED decisions are considered (PENDING /
        BLOCKED / WAIT decisions are excluded — they were never confirmed).
      - Only OPEN_LONG_YES / OPEN_LONG_NO (entry decisions) are included —
        CLOSE_POSITION / WATCH / SKIP are never returned.
      - Exactly one row per condition_id — the most recent by decided_at.
      - Current PENDING decisions cannot appear (they have status PENDING,
        which is excluded), so no self-comparison is possible.
      - Condition_ids not in the provided list are never returned, so old
        rollover condition_ids are always excluded.
    """
    if not condition_ids:
        return {}
    result = await session.execute(
        select(TradeDecision)
        .where(
            TradeDecision.condition_id.in_(condition_ids),
            TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
            TradeDecision.status.in_(["RISK_APPROVED", "EXECUTED"]),
        )
        .order_by(desc(TradeDecision.decided_at))
    )
    rows = list(result.scalars().all())
    # Keep only the newest per condition_id (rows already ordered DESC)
    prev: dict[str, TradeDecision] = {}
    for row in rows:
        if row.condition_id not in prev:
            prev[row.condition_id] = row
    return prev


async def get_decision_stats(session: AsyncSession) -> dict:
    """Return aggregate counts broken down by decision type."""
    result = await session.execute(
        select(TradeDecision.decision, func.count().label("cnt"))
        .group_by(TradeDecision.decision)
    )
    rows = result.all()
    counts: dict[str, int] = {r[0]: r[1] for r in rows}

    total = sum(counts.values())
    avg_score_result = await session.execute(
        select(func.avg(TradeDecision.opportunity_score))
        .where(TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]))
    )
    avg_score = avg_score_result.scalar_one_or_none() or 0.0

    return {
        "total_decisions": total,
        "open_long_yes": counts.get("OPEN_LONG_YES", 0),
        "open_long_no": counts.get("OPEN_LONG_NO", 0),
        "watch": counts.get("WATCH", 0),
        "skip": counts.get("SKIP", 0),
        "avg_score_actionable": round(float(avg_score), 2),
    }
