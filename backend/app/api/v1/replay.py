"""
Replay router — Phase 5: Trade Replay.

GET /replay/{position_id} — full step-by-step replay of a closed trade
GET /replay/dataset        — flat dataset of all closed trades for export / ML
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.evaluation import TradeDatasetResponse, TradeReplayResponse
from app.services.trade_replay_service import TradeReplayService

logger = get_logger(__name__)
router = APIRouter(prefix="/replay", tags=["replay"])

_replay_service = TradeReplayService()


@router.get("/dataset", response_model=TradeDatasetResponse)
async def get_trade_dataset(
    limit: int = Query(default=500, ge=1, le=2000, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Row offset for pagination"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Export all closed trades as a flat dataset.

    Joins evaluation data (quality_score, grade) where available.
    Suitable for external ML pipelines, spreadsheet analysis, or backtesting.
    Paginated via limit/offset.
    """
    data = await _replay_service.get_dataset(session, limit=limit, offset=offset)
    return TradeDatasetResponse(**data)


@router.get("/{position_id}", response_model=TradeReplayResponse)
async def replay_position(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Full step-by-step replay of a single closed trade.

    Reconstructs the decision timeline: strategy decision → entry order fill →
    peak PnL → close decision → position closed.
    Returns 404 if the position does not exist or is not yet closed.
    """
    result = await _replay_service.replay_position(position_id, session)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Position {position_id} not found or is not CLOSED.",
        )

    # Convert TradeEvaluation ORM to schema if present
    evaluation = result.get("evaluation")
    from app.schemas.evaluation import TradeEvaluationSchema
    ev_schema = (
        TradeEvaluationSchema.model_validate(evaluation)
        if evaluation is not None
        else None
    )

    from app.schemas.evaluation import ReplayEvent
    timeline = [ReplayEvent(**e) for e in result["timeline"]]

    return TradeReplayResponse(
        position_id=result["position_id"],
        asset=result["asset"],
        timeframe=result["timeframe"],
        side=result["side"],
        entry_price=result["entry_price"],
        exit_price=result["exit_price"],
        realized_pnl=result["realized_pnl"],
        close_reason=result["close_reason"],
        hold_minutes=result["hold_minutes"],
        evaluation=ev_schema,
        timeline=timeline,
    )
