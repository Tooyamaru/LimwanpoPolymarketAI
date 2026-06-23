"""
Price router — Sprint 9.

Endpoints for reading live CLOB price snapshots.

GET /price/latest          — most recent N snapshots (all markets)
GET /price/active          — latest snapshot per active universe market
GET /price/{condition_id}  — latest snapshot(s) for one condition_id
GET /price/stats           — aggregate statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_universe import MarketUniverse
from app.repositories import market_price_repository as repo
from app.schemas.price import PriceSnapshotResponse, PriceStatsResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/price", tags=["price"])


async def _enrich(
    snapshots: list[MarketPriceSnapshot],
    session: AsyncSession,
) -> list[PriceSnapshotResponse]:
    """Join snapshots with market_universe to add asset/timeframe labels."""
    condition_ids = list({s.condition_id for s in snapshots})
    if not condition_ids:
        return []

    result = await session.execute(
        select(MarketUniverse).where(MarketUniverse.condition_id.in_(condition_ids))
    )
    universe_map: dict[str, MarketUniverse] = {
        u.condition_id: u for u in result.scalars().all()
    }

    out: list[PriceSnapshotResponse] = []
    for snap in snapshots:
        uni = universe_map.get(snap.condition_id)
        out.append(
            PriceSnapshotResponse(
                id=snap.id,
                condition_id=snap.condition_id,
                yes_token_id=snap.yes_token_id,
                no_token_id=snap.no_token_id,
                yes_bid=snap.yes_bid,
                yes_ask=snap.yes_ask,
                yes_mid=snap.yes_mid,
                no_bid=snap.no_bid,
                no_ask=snap.no_ask,
                no_mid=snap.no_mid,
                spread_yes=snap.spread_yes,
                spread_no=snap.spread_no,
                volume=snap.volume,
                liquidity=snap.liquidity,
                captured_at=snap.captured_at,
                asset=uni.asset if uni else None,
                timeframe=uni.timeframe if uni else None,
            )
        )
    return out


@router.get("/latest", response_model=list[PriceSnapshotResponse])
async def get_latest_prices(
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the most recent `limit` price snapshots across all markets."""
    snapshots = await repo.get_latest_snapshot(session, limit=limit)
    return await _enrich(snapshots, session)


@router.get("/active", response_model=list[PriceSnapshotResponse])
async def get_active_prices(
    session: AsyncSession = Depends(get_db_session),
):
    """Return the latest price snapshot for each active universe market."""
    snapshots = await repo.get_latest_active_markets(session)
    return await _enrich(snapshots, session)


@router.get("/stats", response_model=PriceStatsResponse)
async def get_price_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate statistics about stored price snapshots."""
    total = await repo.get_snapshot_count(session)

    active_snaps = await repo.get_latest_active_markets(session)
    active_count = len(active_snaps)

    condition_ids = [s.condition_id for s in active_snaps]
    assets: list[str] = []
    timeframes: list[str] = []

    if condition_ids:
        result = await session.execute(
            select(MarketUniverse.asset, MarketUniverse.timeframe)
            .where(MarketUniverse.condition_id.in_(condition_ids))
            .distinct()
        )
        rows = result.all()
        assets = sorted(set(r[0] for r in rows if r[0]))
        timeframes = sorted(set(r[1] for r in rows if r[1]))

    return PriceStatsResponse(
        total_snapshots=total,
        active_markets_with_data=active_count,
        assets_covered=assets,
        timeframes_covered=timeframes,
    )


@router.get("/{condition_id}", response_model=list[PriceSnapshotResponse])
async def get_price_by_condition(
    condition_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the latest `limit` snapshots for a specific condition_id."""
    snapshots = await repo.get_latest_by_condition(session, condition_id, limit=limit)
    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No price snapshots found for condition_id={condition_id}",
        )
    return await _enrich(snapshots, session)
