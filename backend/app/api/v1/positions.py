"""
Positions router — Layer 8: Position Tracking.

GET /positions/card-summary  — per-active-market PNL/LOTS/IN/OUT (all 12 active markets)
GET /positions               — all positions (newest first)
GET /positions/open          — positions with status OPEN
GET /positions/closed        — positions with status CLOSED (newest first)
GET /positions/history       — closed positions with full exit audit trail
GET /positions/stats         — aggregate PnL and count statistics
GET /positions/{id}          — single position detail
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.repositories import position_repository as repo
from app.repositories import card_summary_repository
from app.schemas.card_summary import CardSummaryItem
from app.schemas.position import PositionResponse, PositionStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/card-summary", response_model=list[CardSummaryItem])
async def get_card_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Per-market (condition_id) PNL / LOTS / IN / OUT aggregation for dashboard cards.

    Returns one row for EVERY currently-active market, even those with no
    positions (has_position=False, total_pnl=None for those).  This ensures
    cards always have a summary object keyed to the CURRENT condition_id,
    never the previous rollover market.

    Multi-entry aware: aggregates across every lot (Position row) and every
    executed fill (Order row) for each market.
    """
    # Fetch all active markets so we can return zero-rows for position-free markets
    active_stmt = select(
        MarketUniverse.condition_id,
        MarketUniverse.asset,
        MarketUniverse.timeframe,
    ).where(MarketUniverse.status == "active")
    active_rows = (await session.execute(active_stmt)).all()
    active_markets = [
        {"condition_id": r[0], "asset": r[1], "timeframe": r[2]}
        for r in active_rows
    ]

    summaries = await card_summary_repository.get_card_summaries(
        session, active_markets=active_markets
    )
    return [CardSummaryItem(**v) for v in summaries.values()]


@router.get("", response_model=list[PositionResponse], response_model_by_alias=True)
async def get_positions(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: OPEN | CLOSED",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all positions, newest first. Optionally filter by status."""
    rows = await repo.get_positions(session, status_filter=status, limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/open", response_model=list[PositionResponse], response_model_by_alias=True)
async def get_open_positions(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all OPEN positions ordered by open time ascending."""
    rows = await repo.get_open_positions(session, limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/closed", response_model=list[PositionResponse], response_model_by_alias=True)
async def get_closed_positions(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return CLOSED positions, newest first."""
    rows = await repo.get_positions(session, status_filter="CLOSED", limit=limit)
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/history", response_model=list[PositionResponse], response_model_by_alias=True)
async def get_position_history(
    limit: int = Query(default=200, ge=1, le=1000),
    asset: Optional[str] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trade history — ALL closed positions across every condition_id (including
    old rollover markets).  Used by the history view; never mixed into current
    card display.

    Includes full exit audit trail: close_reason, exit_price, realized_pnl,
    closed_at, etc.
    """
    from app.models.position import Position
    from sqlalchemy import desc

    stmt = (
        select(Position)
        .where(Position.status == "CLOSED")
        .order_by(desc(Position.closed_at))
        .limit(limit)
    )
    if asset:
        stmt = stmt.where(Position.asset == asset.upper())
    if timeframe:
        stmt = stmt.where(Position.timeframe == timeframe.lower())

    rows = list((await session.execute(stmt)).scalars().all())
    return [PositionResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=PositionStatsResponse, response_model_by_alias=True)
async def get_position_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate position counts and PnL statistics."""
    stats = await repo.get_position_stats(session)
    return PositionStatsResponse(**stats)


@router.get("/{position_id}", response_model=PositionResponse, response_model_by_alias=True)
async def get_position(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Return a single position by its ID."""
    pos = await repo.get_position(session, position_id)
    if pos is None:
        raise HTTPException(
            status_code=404,
            detail=f"Position id={position_id} not found",
        )
    return PositionResponse.model_validate(pos)
