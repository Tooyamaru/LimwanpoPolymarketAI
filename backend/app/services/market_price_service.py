"""
Market price service — Sprint 9.

Orchestrates the price refresh cycle:
  1. Load all active markets from market_universe
  2. For each, call the CLOB client to get live prices
  3. Save a snapshot to market_price_snapshots

Designed to run every PRICE_REFRESH_SECONDS (default 10 s) from
the background scheduler loop added in main.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.services.clob_client import ClobClient, ClobMarketData
from app.repositories import market_price_repository as repo
from app.repositories import universe_repository

logger = get_logger(__name__)


class MarketPriceService:
    """
    Fetches and stores live CLOB prices for all active universe markets.

    Usage::

        service = MarketPriceService()
        result = await service.refresh(session)
        await service.close()
    """

    def __init__(self, clob_client: Optional[ClobClient] = None) -> None:
        self._clob = clob_client or ClobClient()
        self._owns_client = clob_client is None

    async def refresh(self, session: AsyncSession) -> dict:
        """
        Run one price-refresh cycle.

        Returns a summary dict::

            {
                "snapshots_saved": int,
                "errors": int,
                "markets_polled": int,
                "active_count": int,
                "duration_ms": int,
            }
        """
        started = datetime.now(timezone.utc)

        active_markets: list[MarketUniverse] = await universe_repository.get_active_universe(
            session
        )
        active_count = len(active_markets)

        if not active_markets:
            logger.info("No active universe markets — price refresh skipped")
            return {
                "snapshots_saved": 0,
                "errors": 0,
                "markets_polled": 0,
                "active_count": 0,
                "duration_ms": 0,
            }

        snapshots_saved = 0
        errors = 0

        for market in active_markets:
            try:
                data: Optional[ClobMarketData] = await self._clob.get_market(
                    condition_id=market.condition_id,
                    yes_token_id=market.yes_token_id,
                    no_token_id=market.no_token_id,
                )
                if data is None:
                    logger.warning(
                        "CLOB returned no data",
                        condition_id=market.condition_id[:12],
                        asset=market.asset,
                        timeframe=market.timeframe,
                    )
                    errors += 1
                    continue

                await repo.save_snapshot(
                    session,
                    market_universe_id=market.id,
                    condition_id=market.condition_id,
                    yes_token_id=data.yes_token_id,
                    no_token_id=data.no_token_id,
                    yes_bid=data.yes_bid,
                    yes_ask=data.yes_ask,
                    yes_mid=data.yes_mid,
                    no_bid=data.no_bid,
                    no_ask=data.no_ask,
                    no_mid=data.no_mid,
                    spread_yes=data.spread_yes,
                    spread_no=data.spread_no,
                    volume=data.volume,
                    liquidity=data.liquidity,
                )
                snapshots_saved += 1

            except Exception as exc:
                logger.error(
                    "Price refresh error for market",
                    condition_id=market.condition_id[:12],
                    asset=market.asset,
                    timeframe=market.timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        duration_ms = int(elapsed * 1000)

        logger.info(
            "Price refresh complete",
            snapshots_saved=snapshots_saved,
            errors=errors,
            markets_polled=active_count,
            duration_ms=duration_ms,
        )

        return {
            "snapshots_saved": snapshots_saved,
            "errors": errors,
            "markets_polled": active_count,
            "active_count": active_count,
            "duration_ms": duration_ms,
        }

    async def close(self) -> None:
        if self._owns_client:
            await self._clob.close()

    async def __aenter__(self) -> "MarketPriceService":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
