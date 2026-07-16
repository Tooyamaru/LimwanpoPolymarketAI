"""
Decision repository — Decision Engine pipeline, final stage (Decision).

Append-only INSERT, mirroring trade_decision_repository.py's log pattern.
Read-only queries only fetch the latest decision per market or recent
history — this pipeline never mutates any other table.

Phase Next — Decision Engine Intelligence Upgrade:
  create_decision_log gains consensus_score, agreement_level,
  conflict_detected, entry_quality_score parameters.
  get_decision_stats gains conflict_count, consensus_count.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.decision_log import DecisionLog

logger = get_logger(__name__)


async def create_decision_log(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    decision: str,
    confidence: float,
    vote_score: float,
    signal_confidence: Optional[float],
    signal_regime: Optional[str],
    momentum_score: Optional[float],
    momentum_direction: Optional[str],
    trend_score: Optional[float],
    trend_direction: Optional[str],
    volatility_score: Optional[float],
    volatility_regime: Optional[str],
    opportunity_score: Optional[float],
    opportunity_direction: Optional[str],
    risk_score: Optional[float],
    risk_gated: Optional[bool],
    reasons: Optional[str],
    # Phase 1: Consensus Engine
    consensus_score: Optional[float] = None,
    agreement_level: Optional[float] = None,
    conflict_detected: Optional[bool] = None,
    # Phase 3: Entry Quality Engine
    entry_quality_score: Optional[float] = None,
    # Polymarket-first reasoning engines
    market_quality_score: Optional[float] = None,
    market_quality: Optional[str] = None,
    market_confidence: Optional[float] = None,
    market_risk: Optional[str] = None,
    market_context_status: Optional[str] = None,
    market_context_confidence: Optional[float] = None,
    orderbook_direction: Optional[str] = None,
    orderbook_confidence: Optional[float] = None,
    funding_direction: Optional[str] = None,
    funding_confidence: Optional[float] = None,
    news_sentiment: Optional[str] = None,
    news_confidence: Optional[float] = None,
    supporting_engines: Optional[str] = None,
) -> DecisionLog:
    row = DecisionLog(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        decision=decision,
        confidence=round(confidence, 2),
        vote_score=round(vote_score, 4),
        # Phase 1
        consensus_score=round(consensus_score, 2) if consensus_score is not None else None,
        agreement_level=round(agreement_level, 4) if agreement_level is not None else None,
        conflict_detected=conflict_detected,
        # Phase 3
        entry_quality_score=round(entry_quality_score, 2) if entry_quality_score is not None else None,
        # Per-engine breakdown
        signal_confidence=signal_confidence,
        signal_regime=signal_regime,
        momentum_score=momentum_score,
        momentum_direction=momentum_direction,
        trend_score=trend_score,
        trend_direction=trend_direction,
        volatility_score=volatility_score,
        volatility_regime=volatility_regime,
        opportunity_score=opportunity_score,
        opportunity_direction=opportunity_direction,
        risk_score=risk_score,
        risk_gated=risk_gated,
        market_quality_score=market_quality_score,
        market_quality=market_quality,
        market_confidence=market_confidence,
        market_risk=market_risk,
        market_context_status=market_context_status,
        market_context_confidence=market_context_confidence,
        orderbook_direction=orderbook_direction,
        orderbook_confidence=orderbook_confidence,
        funding_direction=funding_direction,
        funding_confidence=funding_confidence,
        news_sentiment=news_sentiment,
        news_confidence=news_confidence,
        supporting_engines=supporting_engines,
        reasons=reasons,
    )
    session.add(row)
    await session.flush()

    logger.debug(
        "Decision log created",
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        decision=decision,
        confidence=round(confidence, 1),
        consensus_score=consensus_score,
        conflict_detected=conflict_detected,
        entry_quality_score=entry_quality_score,
    )
    return row


async def get_latest_decision(
    session: AsyncSession, condition_id: str
) -> Optional[DecisionLog]:
    result = await session.execute(
        select(DecisionLog)
        .where(DecisionLog.condition_id == condition_id)
        .order_by(desc(DecisionLog.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_recent_decisions(
    session: AsyncSession, limit: int = 50
) -> list[DecisionLog]:
    result = await session.execute(
        select(DecisionLog).order_by(desc(DecisionLog.created_at)).limit(limit)
    )
    return list(result.scalars().all())


async def get_decision_stats(session: AsyncSession) -> dict:
    """
    Aggregate counts of the most recent decision per market.

    Phase 8 — Engine Health:
      Returns BUY_YES / BUY_NO / WAIT / conflict_count / consensus_count
      and avg_confidence, avg_entry_quality per the latest decision per market.
    """
    # Get the latest decision id per market
    latest_ids_stmt = (
        select(
            DecisionLog.condition_id,
            func.max(DecisionLog.id).label("max_id"),
        ).group_by(DecisionLog.condition_id)
    )
    latest_ids_result = await session.execute(latest_ids_stmt)
    max_ids = [row.max_id for row in latest_ids_result.all()]

    if not max_ids:
        return {
            "total_markets": 0,
            "buy_yes_count": 0,
            "buy_no_count": 0,
            "wait_count": 0,
            "conflict_count": 0,
            "consensus_count": 0,
            "avg_confidence": 0.0,
            "avg_entry_quality": 0.0,
        }

    result = await session.execute(
        select(DecisionLog).where(DecisionLog.id.in_(max_ids))
    )
    rows = list(result.scalars().all())

    buy_yes = sum(1 for r in rows if r.decision == "BUY_YES")
    buy_no = sum(1 for r in rows if r.decision == "BUY_NO")
    wait = sum(1 for r in rows if r.decision == "WAIT")

    # Phase 1 — Consensus Engine stats
    conflict_count = sum(1 for r in rows if r.conflict_detected is True)
    # "consensus" = agreement_level >= 0.70 (most engines agree)
    consensus_count = sum(
        1 for r in rows
        if r.agreement_level is not None and r.agreement_level >= 0.70
    )

    avg_confidence = round(sum(r.confidence for r in rows) / len(rows), 2)

    # Phase 3 — Entry Quality stats
    entry_qualities = [r.entry_quality_score for r in rows if r.entry_quality_score is not None]
    avg_entry_quality = round(sum(entry_qualities) / len(entry_qualities), 2) if entry_qualities else 0.0

    return {
        "total_markets": len(rows),
        "buy_yes_count": buy_yes,
        "buy_no_count": buy_no,
        "wait_count": wait,
        "conflict_count": conflict_count,
        "consensus_count": consensus_count,
        "avg_confidence": avg_confidence,
        "avg_entry_quality": avg_entry_quality,
    }
