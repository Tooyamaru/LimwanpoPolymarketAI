"""
Discovery API — Sprint 3.

GET  /api/v1/discovery         — latest discovery run diagnostics
POST /api/v1/discovery/run     — trigger an on-demand discovery run
GET  /api/v1/discovery/markets — all markets matched in the latest run
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.discovery_run import DiscoveryRun
from app.models.scanner_market import ScannerMarket
from app.schemas.discovery import DiscoveryDiagnosticsResponse, DiscoveryMarketResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get(
    "",
    response_model=DiscoveryDiagnosticsResponse,
    summary="Latest discovery run diagnostics",
)
async def get_discovery_diagnostics(
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryDiagnosticsResponse:
    """
    Returns stats from the most recent market discovery run.
    """
    result = await session.execute(
        select(DiscoveryRun).order_by(DiscoveryRun.run_at.desc()).limit(1)
    )
    run = result.scalar_one_or_none()

    if run is None:
        return DiscoveryDiagnosticsResponse(
            run_at=None,
            total_markets_scanned=0,
            matched_markets=0,
            btc=0,
            eth=0,
            sol=0,
            xrp=0,
        )

    return DiscoveryDiagnosticsResponse(
        run_at=run.run_at,
        total_markets_scanned=run.total_scanned,
        matched_markets=run.total_matched,
        btc=run.btc_count,
        eth=run.eth_count,
        sol=run.sol_count,
        xrp=run.xrp_count,
    )


@router.post(
    "/run",
    response_model=DiscoveryDiagnosticsResponse,
    summary="Trigger an on-demand discovery scan",
)
async def run_discovery_now() -> DiscoveryDiagnosticsResponse:
    """
    Runs a full market discovery scan immediately and returns the result.
    Blocking — expect 10–30 seconds depending on Polymarket pagination depth.
    """
    from app.services.scanner import ScannerService
    scanner = ScannerService()
    try:
        result = await scanner.run()
    finally:
        await scanner.close()

    return DiscoveryDiagnosticsResponse(
        run_at=result.run_at,
        total_markets_scanned=result.total_scanned,
        matched_markets=result.total_matched,
        btc=result.btc_count,
        eth=result.eth_count,
        sol=result.sol_count,
        xrp=result.xrp_count,
    )


@router.get(
    "/markets",
    response_model=list[DiscoveryMarketResponse],
    summary="All matched markets with full transparency metadata",
)
async def get_discovery_markets(
    asset: Optional[str] = None,
    timeframe: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[DiscoveryMarketResponse]:
    """
    Returns every market in the scanner universe with the full transparency
    record showing WHY it was matched (raw_title, matching_rule, detected_asset,
    detected_timeframe).
    """
    stmt = select(ScannerMarket).order_by(ScannerMarket.asset, ScannerMarket.timeframe)
    if asset:
        stmt = stmt.where(ScannerMarket.asset == asset.upper())
    if timeframe:
        stmt = stmt.where(ScannerMarket.timeframe == timeframe)

    result = await session.execute(stmt)
    markets = result.scalars().all()
    return [DiscoveryMarketResponse.model_validate(m) for m in markets]
