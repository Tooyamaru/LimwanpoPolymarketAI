"""
Opportunities router — Layer 5: Opportunity Engine.

GET /opportunities              — all markets with current scores
GET /opportunities/top          — top N by score
GET /opportunities/stats        — aggregate summary
GET /opportunities/{condition_id} — single market detail
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services import opportunity_repository as repo

logger = get_logger(__name__)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


# ── Response schemas ───────────────────────────────────────────────────────────

class OpportunityResponse(BaseModel):
    id: int
    condition_id: str
    asset: str
    timeframe: str

    opportunity_score: float

    score_mid_movement: float
    score_spread: float
    score_depth_imbalance: float
    score_signal_activity: float
    score_discovery: float

    yes_mid: Optional[float]
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    no_mid: Optional[float]
    spread_yes: Optional[float]
    spread_no: Optional[float]
    seed_deviation: Optional[float]

    signal_count_1h: int
    last_signal_type: Optional[str]
    last_signal_severity: Optional[str]

    minutes_to_expiry: Optional[float]
    direction: str
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class OpportunityStatsResponse(BaseModel):
    total_markets: int
    markets_with_direction: int
    avg_score: float
    top_score: float
    top_asset: Optional[str]
    top_timeframe: Optional[str]
    buy_yes_count: int
    buy_no_count: int
    neutral_count: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[OpportunityResponse])
async def get_all_opportunities(
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Return all markets with their current Opportunity Scores, sorted best first.
    Optionally filter by minimum score via `min_score`.
    """
    opps = await repo.get_all_opportunities(session, min_score=min_score)
    return [OpportunityResponse.model_validate(o) for o in opps]


@router.get("/top", response_model=list[OpportunityResponse])
async def get_top_opportunities(
    limit: int = Query(default=5, ge=1, le=20),
    min_score: float = Query(default=10.0, ge=0.0, le=100.0),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the top `limit` opportunities with score >= `min_score`."""
    opps = await repo.get_top_opportunities(session, limit=limit, min_score=min_score)
    return [OpportunityResponse.model_validate(o) for o in opps]


@router.get("/stats", response_model=OpportunityStatsResponse)
async def get_opportunity_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate statistics across all tracked opportunities."""
    all_opps = await repo.get_all_opportunities(session, min_score=0.0)

    if not all_opps:
        return OpportunityStatsResponse(
            total_markets=0,
            markets_with_direction=0,
            avg_score=0.0,
            top_score=0.0,
            top_asset=None,
            top_timeframe=None,
            buy_yes_count=0,
            buy_no_count=0,
            neutral_count=0,
        )

    total = len(all_opps)
    avg_score = round(sum(o.opportunity_score for o in all_opps) / total, 2)
    top = all_opps[0]

    buy_yes = sum(1 for o in all_opps if o.direction == "BUY_YES")
    buy_no = sum(1 for o in all_opps if o.direction == "BUY_NO")
    neutral = sum(1 for o in all_opps if o.direction == "NEUTRAL")
    with_dir = buy_yes + buy_no

    return OpportunityStatsResponse(
        total_markets=total,
        markets_with_direction=with_dir,
        avg_score=avg_score,
        top_score=top.opportunity_score,
        top_asset=top.asset,
        top_timeframe=top.timeframe,
        buy_yes_count=buy_yes,
        buy_no_count=buy_no,
        neutral_count=neutral,
    )


@router.get("/{condition_id}", response_model=OpportunityResponse)
async def get_opportunity_by_condition(
    condition_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Return the current opportunity assessment for a specific condition_id."""
    opp = await repo.get_opportunity_by_condition(session, condition_id)
    if opp is None:
        raise HTTPException(
            status_code=404,
            detail=f"No opportunity record found for condition_id={condition_id}",
        )
    return OpportunityResponse.model_validate(opp)
