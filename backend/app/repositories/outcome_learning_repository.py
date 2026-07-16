"""outcome_learning_repository.py — Outcome Learning persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.outcome_learning import OutcomeLearning

logger = get_logger(__name__)


async def upsert_outcome(
    session: AsyncSession,
    *,
    condition_id: str,
    asset: str,
    timeframe: str,
    prediction: str,
    outcome_type: str,
    correct: Optional[bool],
    actual_pnl: Optional[float] = None,
    decision_log_id: Optional[int] = None,
    confidence: Optional[float] = None,
    consensus_score: Optional[float] = None,
    agreement_level: Optional[float] = None,
    conflict_detected: Optional[bool] = None,
    entry_quality_score: Optional[float] = None,
    market_quality: Optional[str] = None,
    market_quality_score: Optional[float] = None,
    vote_score: Optional[float] = None,
    opportunity_direction: Optional[str] = None,
    orderbook_direction: Optional[str] = None,
    momentum_direction: Optional[str] = None,
    trend_direction: Optional[str] = None,
    funding_direction: Optional[str] = None,
    confidence_calibration: Optional[str] = None,
    entry_quality_evaluation: Optional[str] = None,
    consensus_evaluation: Optional[str] = None,
    feedback_summary: Optional[str] = None,
    position_id: Optional[int] = None,
    market_title: Optional[str] = None,
    market_type: Optional[str] = None,
    entry_timestamp: Optional[datetime] = None,
    close_timestamp: Optional[datetime] = None,
    ai_score: Optional[float] = None,
    # Phase 9D: Direct Polymarket resolution fields
    outcome_source: Optional[str] = None,
    winning_side: Optional[str] = None,
    winning_token_id: Optional[str] = None,
    final_yes_price: Optional[float] = None,
    final_no_price: Optional[float] = None,
    resolution_note: Optional[str] = None,
) -> OutcomeLearning:
    """UPSERT by condition_id — one record per market (append-once, update on re-evaluation)."""
    stmt = (
        pg_insert(OutcomeLearning)
        .values(
            condition_id=condition_id,
            asset=asset,
            timeframe=timeframe,
            prediction=prediction,
            outcome_type=outcome_type,
            correct=correct,
            actual_pnl=actual_pnl,
            decision_log_id=decision_log_id,
            confidence=confidence,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            conflict_detected=conflict_detected,
            entry_quality_score=entry_quality_score,
            market_quality=market_quality,
            market_quality_score=market_quality_score,
            vote_score=vote_score,
            opportunity_direction=opportunity_direction,
            orderbook_direction=orderbook_direction,
            momentum_direction=momentum_direction,
            trend_direction=trend_direction,
            funding_direction=funding_direction,
            confidence_calibration=confidence_calibration,
            entry_quality_evaluation=entry_quality_evaluation,
            consensus_evaluation=consensus_evaluation,
            feedback_summary=feedback_summary,
            position_id=position_id,
            market_title=market_title,
            market_type=market_type,
            entry_timestamp=entry_timestamp,
            close_timestamp=close_timestamp,
            ai_score=ai_score,
            outcome_source=outcome_source,
            winning_side=winning_side,
            winning_token_id=winning_token_id,
            final_yes_price=final_yes_price,
            final_no_price=final_no_price,
            resolution_note=resolution_note,
            evaluated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["condition_id"],
            set_={
                "prediction": prediction,
                "outcome_type": outcome_type,
                "correct": correct,
                "actual_pnl": actual_pnl,
                "confidence": confidence,
                "consensus_score": consensus_score,
                "agreement_level": agreement_level,
                "conflict_detected": conflict_detected,
                "entry_quality_score": entry_quality_score,
                "market_quality": market_quality,
                "market_quality_score": market_quality_score,
                "vote_score": vote_score,
                "opportunity_direction": opportunity_direction,
                "orderbook_direction": orderbook_direction,
                "momentum_direction": momentum_direction,
                "trend_direction": trend_direction,
                "funding_direction": funding_direction,
                "confidence_calibration": confidence_calibration,
                "entry_quality_evaluation": entry_quality_evaluation,
                "consensus_evaluation": consensus_evaluation,
                "feedback_summary": feedback_summary,
                "position_id": position_id,
                "market_title": market_title,
                "market_type": market_type,
                "entry_timestamp": entry_timestamp,
                "close_timestamp": close_timestamp,
                "ai_score": ai_score,
                "outcome_source": outcome_source,
                "winning_side": winning_side,
                "winning_token_id": winning_token_id,
                "final_yes_price": final_yes_price,
                "final_no_price": final_no_price,
                "resolution_note": resolution_note,
                "evaluated_at": datetime.now(timezone.utc),
            },
        )
        .returning(OutcomeLearning)
    )
    result = await session.execute(stmt)
    row = result.scalar_one()
    logger.debug(
        "Outcome upserted",
        condition_id=condition_id,
        prediction=prediction,
        correct=correct,
        outcome_type=outcome_type,
        outcome_source=outcome_source,
    )
    return row


async def get_recent_outcomes(
    session: AsyncSession, limit: int = 50
) -> list[OutcomeLearning]:
    result = await session.execute(
        select(OutcomeLearning)
        .order_by(desc(OutcomeLearning.evaluated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_outcome_stats(session: AsyncSession) -> dict:
    """Aggregate outcome statistics for the feedback dashboard."""
    result = await session.execute(select(OutcomeLearning))
    rows = list(result.scalars().all())

    if not rows:
        return {
            "total_evaluated": 0,
            "with_position": 0,
            "correct": 0,
            "wrong": 0,
            "unknown": 0,
            "accuracy": 0.0,
            "avg_confidence_when_correct": 0.0,
            "avg_confidence_when_wrong": 0.0,
            "overconfident_count": 0,
            "underconfident_count": 0,
        }

    total = len(rows)
    with_pos = sum(1 for r in rows if r.outcome_type == "POSITION")
    correct = sum(1 for r in rows if r.correct is True)
    wrong = sum(1 for r in rows if r.correct is False)
    unknown = sum(1 for r in rows if r.correct is None)

    decided = correct + wrong
    accuracy = round(correct / decided * 100.0, 2) if decided > 0 else 0.0

    conf_correct = [r.confidence for r in rows if r.correct is True and r.confidence is not None]
    conf_wrong = [r.confidence for r in rows if r.correct is False and r.confidence is not None]

    avg_conf_correct = round(sum(conf_correct) / len(conf_correct), 2) if conf_correct else 0.0
    avg_conf_wrong   = round(sum(conf_wrong)   / len(conf_wrong),   2) if conf_wrong   else 0.0

    overconfident = sum(
        1 for r in rows if r.confidence_calibration == "OVERCONFIDENT"
    )
    underconfident = sum(
        1 for r in rows if r.confidence_calibration == "UNDERCONFIDENT"
    )

    return {
        "total_evaluated": total,
        "with_position": with_pos,
        "correct": correct,
        "wrong": wrong,
        "unknown": unknown,
        "accuracy": accuracy,
        "avg_confidence_when_correct": avg_conf_correct,
        "avg_confidence_when_wrong": avg_conf_wrong,
        "overconfident_count": overconfident,
        "underconfident_count": underconfident,
    }


async def get_outcome_by_condition_id(
    session: AsyncSession, condition_id: str
) -> Optional[OutcomeLearning]:
    result = await session.execute(
        select(OutcomeLearning).where(OutcomeLearning.condition_id == condition_id)
    )
    return result.scalar_one_or_none()


async def already_evaluated(session: AsyncSession, condition_id: str) -> bool:
    """Return True if this market has already been evaluated."""
    result = await session.execute(
        select(func.count(OutcomeLearning.id)).where(
            OutcomeLearning.condition_id == condition_id
        )
    )
    return (result.scalar_one() or 0) > 0


async def get_outcomes_filtered(
    session: AsyncSession,
    *,
    asset: Optional[str] = None,
    timeframe: Optional[str] = None,
    market_type: Optional[str] = None,
    limit: int = 200,
) -> list[OutcomeLearning]:
    """
    Priority 1 — query outcome_learnings filtered by any combination of
    asset / timeframe / market_type. `condition_id` filtering is already
    covered by get_outcome_by_condition_id (one row per market).
    """
    stmt = select(OutcomeLearning)
    if asset:
        stmt = stmt.where(OutcomeLearning.asset == asset)
    if timeframe:
        stmt = stmt.where(OutcomeLearning.timeframe == timeframe)
    if market_type:
        stmt = stmt.where(OutcomeLearning.market_type == market_type)
    stmt = stmt.order_by(desc(OutcomeLearning.evaluated_at)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_outcomes(session: AsyncSession) -> list[OutcomeLearning]:
    """Return all outcome_learnings rows — used by calibration/market-type recompute."""
    result = await session.execute(select(OutcomeLearning))
    return list(result.scalars().all())
