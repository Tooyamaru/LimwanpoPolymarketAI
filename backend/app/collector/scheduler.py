"""
Collector scheduler — Sprint 2.

Runs on a fixed interval:
  1. Fetch Binance Spot ticker data
  2. Fetch Polymarket active markets
  3. Match assets, persist to PostgreSQL via market_repository

Interval: COLLECTOR_INTERVAL_SECONDS (default 5 s)
"""

import asyncio
from datetime import datetime, timezone

from app.collector.binance_spot import BinanceSpotCollector
from app.collector.polymarket import PolymarketCollector
from app.config.settings import settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.repositories.market_repository import (
    get_active_markets,
    save_market,
    save_snapshot,
)

logger = get_logger(__name__)


class CollectorScheduler:
    """
    Orchestrates Binance + Polymarket collectors on a fixed interval.

    Usage (from FastAPI lifespan):
        scheduler = CollectorScheduler()
        task = asyncio.create_task(scheduler.run())
        ...
        scheduler.stop()
        await task
    """

    def __init__(self, interval: int | None = None) -> None:
        self.interval = interval or settings.COLLECTOR_INTERVAL_SECONDS
        self._running = False
        self._binance = BinanceSpotCollector()
        self._polymarket = PolymarketCollector()

    async def _tick(self) -> None:
        """Execute one collection cycle."""
        now = datetime.now(timezone.utc)

        # ── Step 1: Binance ──────────────────────────────────────────────────
        binance_data: dict[str, float] = {}
        try:
            tickers = await self._binance.fetch()
            # Build asset → price lookup (strip USDT suffix for matching)
            binance_data = {
                t.symbol.replace("USDT", ""): t.last_price for t in tickers
            }
            logger.debug("Binance data fetched", assets=list(binance_data.keys()))
        except Exception as exc:
            logger.error("Binance fetch failed", error=str(exc))

        # ── Step 2: Polymarket ───────────────────────────────────────────────
        poly_markets = []
        try:
            poly_markets = await self._polymarket.fetch()
            logger.debug("Polymarket data fetched", count=len(poly_markets))
        except Exception as exc:
            logger.error("Polymarket fetch failed", error=str(exc))

        if not poly_markets:
            logger.info("No Polymarket markets matched — skipping DB write")
            return

        # ── Step 3: Persist ──────────────────────────────────────────────────
        factory = get_session_factory()
        async with factory() as session:
            try:
                saved = 0
                for pm in poly_markets:
                    market = await save_market(
                        session,
                        asset=pm.asset,
                        timeframe=pm.timeframe,
                        polymarket_market_id=pm.market_id,
                        title=pm.title,
                        end_time=pm.end_time,
                        start_time=now,
                    )

                    binance_price = binance_data.get(pm.asset)

                    await save_snapshot(
                        session,
                        market_id=market.id,
                        timestamp=now,
                        yes_price=pm.yes_price,
                        no_price=pm.no_price,
                        liquidity=pm.liquidity,
                        volume=pm.volume,
                        binance_price=binance_price,
                    )
                    saved += 1

                await session.commit()
                logger.info(
                    "Collector tick complete",
                    snapshots_saved=saved,
                    binance_assets=len(binance_data),
                )
            except Exception as exc:
                await session.rollback()
                logger.error("DB persist failed", error=str(exc))

    async def run(self) -> None:
        """Main loop — runs until stop() is called."""
        self._running = True
        logger.info("Collector scheduler started", interval_seconds=self.interval)

        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                logger.error("Unexpected error in collector tick", error=str(exc))

            await asyncio.sleep(self.interval)

        logger.info("Collector scheduler stopped")

    def stop(self) -> None:
        self._running = False

    async def close(self) -> None:
        self.stop()
        await self._binance.close()
        await self._polymarket.close()
