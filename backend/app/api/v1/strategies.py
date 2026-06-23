"""
Strategies router — Layer 6: Strategy Engine.

GET /strategies          — recent trade decisions (all types)
GET /strategies/active   — actionable decisions (OPEN_LONG_YES / OPEN_LONG_NO, PENDING)
GET /strategies/stats    — aggregate decision counts and averages
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services import trade_decision_repository as repo

logger = get_logger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ── Response schemas ───────────────────────────────────────────────────────────

class TradeDecisionResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    decision: str
    status: str

    opportunity_score: float
    direction: str

    yes_mid: Optional[float]
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    spread_yes: Optional[float]

    skip_reason: Optional[str]
    decided_at: datetime

    model_config = {"from_attributes": True}


class StrategyStatsResponse(BaseModel):
    total_decisions: int
    open_long_yes: int
    open_long_no: int
    watch: int
    skip: int
    avg_score_actionable: float


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TradeDecisionResponse])
async def get_decisions(
    decision: Optional[str] = Query(
        default=None,
        description="Filter by decision type: OPEN_LONG_YES | OPEN_LONG_NO | WATCH | SKIP",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Return recent trade decisions, newest first.
    Optionally filter by decision type via the `decision` query parameter.
    """
    rows = await repo.get_all_decisions(session, decision_filter=decision, limit=limit)
    return [TradeDecisionResponse.model_validate(r) for r in rows]


@router.get("/active", response_model=list[TradeDecisionResponse])
async def get_active_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Return actionable decisions (OPEN_LONG_YES / OPEN_LONG_NO) with status PENDING,
    sorted by opportunity score descending.
    """
    rows = await repo.get_active_decisions(session, limit=limit)
    return [TradeDecisionResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=StrategyStatsResponse)
async def get_strategy_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate counts and average score across all trade decisions."""
    stats = await repo.get_decision_stats(session)
    return StrategyStatsResponse(**stats)
