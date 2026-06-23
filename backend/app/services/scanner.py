"""
Scanner Engine — Sprint 3 / Sprint 4.

Builds and maintains the active market universe by orchestrating the discovery
engine and persisting results to the scanner_markets table.

Sprint 4 change: scanner now filters to UPDOWN markets ONLY.
All other event types (PRICE_RANGE, NEWS_EVENT, POLITICS, OTHER) are
classified and stored in event_classifications but are NOT promoted to
the scanner_markets universe.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.repositories.event_classification_repository import save_classification
from app.services.market_discovery import DiscoveryResult, MarketDiscoveryService
from app.repositories.scanner_repository import (
    mark_stale_markets,
    save_scanner_market,
)

logger = get_logger(__name__)

UPDOWN = "UPDOWN"


class ScannerService:
    """
    Orchestrates discovery → classification → persistence.

    Flow per scan cycle:
      1. Discover all active Polymarket markets (asset+timeframe filtered).
      2. Save EventClassification row for every matched market.
      3. Promote UPDOWN markets to scanner_markets (active universe).
      4. Mark scanner_markets entries no longer UPDOWN as stale.
      5. Persist discovery run diagnostics (including classification stats).
    """

    def __init__(self) -> None:
        self._discovery = MarketDiscoveryService()

    async def run(self) -> DiscoveryResult:
        result = await self._discovery.discover()

        factory = get_session_factory()
        async with factory() as session:
            try:
                now = datetime.now(timezone.utc)
                updown_ids: set[str] = set()

                for mm in result.matched_markets:
                    # ── Step 1: persist classification for every matched market ──
                    await save_classification(
                        session,
                        market_id=mm.market_id,
                        raw_title=mm.raw_title,
                        event_type=mm.event_type,
                        confidence=mm.confidence,
                        matched_rule=mm.classification_rule,
                        created_at=now,
                    )

                    # ── Step 2: promote UPDOWN → scanner universe ──────────────
                    if mm.event_type == UPDOWN:
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
                        updown_ids.add(mm.market_id)

                # ── Step 3: mark stale scanner markets ────────────────────────
                await mark_stale_markets(session, active_ids=updown_ids)

                # ── Step 4: persist discovery run (with classification stats) ──
                from app.models.discovery_run import DiscoveryRun
                run_row = DiscoveryRun(
                    run_at=result.run_at,
                    total_scanned=result.total_scanned,
                    total_matched=result.total_matched,
                    btc_count=result.btc_count,
                    eth_count=result.eth_count,
                    sol_count=result.sol_count,
                    xrp_count=result.xrp_count,
                    updown_count=result.updown_count,
                    price_range_count=result.price_range_count,
                    news_event_count=result.news_event_count,
                    politics_count=result.politics_count,
                    other_count=result.other_count,
                )
                session.add(run_row)
                await session.commit()

                updown_total = len(updown_ids)
                logger.info(
                    "Scanner run complete",
                    total_matched=result.total_matched,
                    updown_promoted=updown_total,
                    other_classified=result.total_matched - updown_total,
                )

            except Exception as exc:
                await session.rollback()
                logger.error("Scanner DB persist failed", error=str(exc))

        return result

    async def close(self) -> None:
        await self._discovery.close()
