"""
Scanner Engine — Sprint 3.

Builds and maintains the active market universe by orchestrating the discovery
engine and persisting results to the scanner_markets table.

The scanner runs on its own cadence (SCANNER_INTERVAL_SECONDS), independently
from the 5-second price-collection tick.

Output per matched market:
    ScannerMarket
        asset
        timeframe
        market_id
        health_status
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.market_discovery import DiscoveryResult, MarketDiscoveryService, MatchedMarket
from app.services.scanner_repository import (
    get_scanner_markets,
    save_scanner_market,
    mark_stale_markets,
)

logger = get_logger(__name__)


@dataclass
class ScannerMarket:
    """In-memory representation of one scanner universe entry."""
    asset: str
    timeframe: str
    market_id: str
    health_status: str
    raw_title: str
    matching_rule: str
    detected_asset: str
    detected_timeframe: str


class ScannerService:
    """
    Orchestrates discovery → persistence.

    Call run() once per scan cycle.  Returns the ScannerResult summary.
    """

    def __init__(self) -> None:
        self._discovery = MarketDiscoveryService()

    async def run(self) -> DiscoveryResult:
        """
        Execute one full scan:
        1. Discover all active Polymarket markets.
        2. Upsert matched markets into scanner_markets table.
        3. Mark any previously-seen markets that are no longer active as stale.
        4. Persist the discovery run diagnostics.
        5. Return the full DiscoveryResult.
        """
        result = await self._discovery.discover()

        factory = get_session_factory()
        async with factory() as session:
            try:
                now = datetime.now(timezone.utc)
                seen_ids: set[str] = set()

                for mm in result.matched_markets:
                    await save_scanner_market(
                        session,
                        asset=mm.asset,
                        timeframe=mm.timeframe,
                        market_id=mm.market_id,
                        health_status="active",
                        created_at=now,
                        raw_title=mm.raw_title,
                        matching_rule=mm.matching_rule,
                        detected_asset=mm.detected_asset,
                        detected_timeframe=mm.detected_timeframe,
                    )
                    seen_ids.add(mm.market_id)

                # Mark markets no longer returned by the API as stale
                await mark_stale_markets(session, active_ids=seen_ids)

                # Persist discovery diagnostics
                from app.models.discovery_run import DiscoveryRun
                run_row = DiscoveryRun(
                    run_at=result.run_at,
                    total_scanned=result.total_scanned,
                    total_matched=result.total_matched,
                    btc_count=result.btc_count,
                    eth_count=result.eth_count,
                    sol_count=result.sol_count,
                    xrp_count=result.xrp_count,
                )
                session.add(run_row)
                await session.commit()

                logger.info(
                    "Scanner run persisted",
                    matched=result.total_matched,
                    stale_candidates=len(seen_ids),
                )
            except Exception as exc:
                await session.rollback()
                logger.error("Scanner DB persist failed", error=str(exc))

        return result

    async def close(self) -> None:
        await self._discovery.close()
