"""
Trades router — Phase 5: Closed trades listing with evaluation data.

GET /trades           — paginated list of all closed trades + quality scores
GET /trades/{id}      — single closed trade detail with full evaluation
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.position import Position
from app.models.trade_evaluation import TradeEvaluation
from app.schemas.evaluation import TradeSummaryRow, TradesListResponse
from app.services.trade_evaluation_service import TradeEvaluationService

logger = get_logger(__name__)
router = APIRouter(prefix="/trades", tags=["trades"])

_eval_service = TradeEvaluationService()


def _hold_minutes(pos: Position) -> Optional[float]:
    from datetime import timezone
    if pos.opened_at is None or pos.closed_at is None:
        return None
    opened = pos.opened_at
    closed = pos.closed_at
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    if closed.tzinfo is None:
        closed = closed.replace(tzinfo=timezone.utc)
    return round((closed - opened).total_seconds() / 60.0, 4)


@router.get("", response_model=TradesListResponse)
async def list_trades(
    limit: int = Query(default=50, ge=1, le=500, description="Max rows per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    asset: Optional[str] = Query(default=None, description="Filter by asset (BTC/ETH/SOL/XRP)"),
    timeframe: Optional[str] = Query(default=None, description="Filter by timeframe (5m/15m/1H)"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Paginated list of all closed trades with evaluation quality scores.

    Optionally filter by asset or timeframe.
    Quality scores are null for positions not yet evaluated — run
    POST /evaluation/run to populate them.
    """
    query = select(Position).where(Position.status == "CLOSED")
    if asset:
        query = query.where(Position.asset == asset.upper())
    if timeframe:
        query = query.where(Position.timeframe == timeframe)

    # Total count (without pagination)
    from sqlalchemy import func
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_res = await session.execute(count_query)
    total: int = total_res.scalar_one() or 0

    # Paginated positions
    paged_query = (
        query.order_by(Position.closed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    pos_res = await session.execute(paged_query)
    positions: list[Position] = list(pos_res.scalars().all())

    # Fetch evaluations for these positions
    if positions:
        pos_ids = [p.id for p in positions]
        eval_res = await session.execute(
            select(TradeEvaluation).where(TradeEvaluation.position_id.in_(pos_ids))
        )
        evals: dict[int, TradeEvaluation] = {
            ev.position_id: ev for ev in eval_res.scalars().all()
        }
    else:
        evals = {}

    rows: list[TradeSummaryRow] = []
    for pos in positions:
        ev = evals.get(pos.id)
        rows.append(TradeSummaryRow(
            position_id=pos.id,
            asset=pos.asset,
            timeframe=pos.timeframe,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=pos.exit_price,
            realized_pnl=pos.realized_pnl,
            total_fee_usdc=getattr(pos, "total_fee_usdc", None),
            close_reason=pos.close_reason,
            hold_minutes=_hold_minutes(pos),
            opened_at=pos.opened_at,
            closed_at=pos.closed_at,
            quality_score=ev.quality_score if ev else None,
            grade=ev.grade if ev else None,
        ))

    return TradesListResponse(total=total, limit=limit, offset=offset, trades=rows)


@router.get("/{position_id}", response_model=TradeSummaryRow)
async def get_trade(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Single closed trade with evaluation data.

    Returns 404 if not found or not yet closed.
    """
    from fastapi import HTTPException

    pos_res = await session.execute(
        select(Position).where(
            Position.id == position_id,
            Position.status == "CLOSED",
        )
    )
    pos: Optional[Position] = pos_res.scalar_one_or_none()
    if pos is None:
        raise HTTPException(
            status_code=404,
            detail=f"Closed position {position_id} not found.",
        )

    ev_res = await session.execute(
        select(TradeEvaluation).where(TradeEvaluation.position_id == position_id)
    )
    ev: Optional[TradeEvaluation] = ev_res.scalar_one_or_none()

    return TradeSummaryRow(
        position_id=pos.id,
        asset=pos.asset,
        timeframe=pos.timeframe,
        side=pos.side,
        entry_price=pos.entry_price,
        exit_price=pos.exit_price,
        realized_pnl=pos.realized_pnl,
        total_fee_usdc=getattr(pos, "total_fee_usdc", None),
        close_reason=pos.close_reason,
        hold_minutes=_hold_minutes(pos),
        opened_at=pos.opened_at,
        closed_at=pos.closed_at,
        quality_score=ev.quality_score if ev else None,
        grade=ev.grade if ev else None,
    )
