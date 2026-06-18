"""
Market Universe Service — Sprint 7.

Syncs all 12 known Gamma Series into the market_universe table.
Determines status (active / upcoming / expired) for each market
and keeps the universe current on every sync cycle.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.gamma_series_client import GammaSeriesClient
from app.services.universe_repository import expire_stale_markets, upsert_universe_market

logger = get_logger(__name__)


# ── Known series catalog ───────────────────────────────────────────────────────

SERIES_CATALOG: list[dict] = [
    {"slug": "btc-up-or-down-5m",        "asset": "BTC", "timeframe": "5m"},
    {"slug": "eth-up-or-down-5m",        "asset": "ETH", "timeframe": "5m"},
    {"slug": "sol-up-or-down-5m",        "asset": "SOL", "timeframe": "5m"},
    {"slug": "xrp-up-or-down-5m",        "asset": "XRP", "timeframe": "5m"},
    {"slug": "btc-up-or-down-15m",       "asset": "BTC", "timeframe": "15m"},
    {"slug": "eth-up-or-down-15m",       "asset": "ETH", "timeframe": "15m"},
    {"slug": "sol-up-or-down-15m",       "asset": "SOL", "timeframe": "15m"},
    {"slug": "xrp-up-or-down-15m",       "asset": "XRP", "timeframe": "15m"},
    {"slug": "btc-up-or-down-hourly",    "asset": "BTC", "timeframe": "1H"},
    {"slug": "eth-up-or-down-hourly",    "asset": "ETH", "timeframe": "1H"},
    {"slug": "solana-up-or-down-hourly", "asset": "SOL", "timeframe": "1H"},
    {"slug": "xrp-up-or-down-hourly",    "asset": "XRP", "timeframe": "1H"},
]


def _determine_status(
    is_active: bool,
    is_closed: bool,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
) -> str:
    """
    Map Gamma API flags + timestamps to our three-state status.

      active   — currently running market
      upcoming — not yet started
      expired  — closed or end_time passed
    """
    now = datetime.now(timezone.utc)

    if is_closed:
        return "expired"
    if end_time and end_time < now:
        return "expired"
    if is_active:
        return "active"
    if start_time and start_time > now:
        return "upcoming"
    return "upcoming"


class MarketUniverseService:
    """
    Orchestrates a full universe sync across all 12 known series.

    Usage (from FastAPI lifespan or scheduler):
        service = MarketUniverseService()
        result = await service.sync()
        await service.close()
    """

    def __init__(self) -> None:
        self._client = GammaSeriesClient()
        self._last_sync: Optional[datetime] = None
        self._last_sync_duration_ms: Optional[float] = None

    async def sync(self) -> dict:
        """
        Sync the entire universe.  Returns a summary dict.
        Target: completes in under 10 seconds for all 12 series.
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Universe sync started", series_count=len(SERIES_CATALOG))

        total_upserted = 0
        total_expired_by_time = 0
        errors: list[str] = []

        factory = get_session_factory()

        for entry in SERIES_CATALOG:
            slug = entry["slug"]
            asset = entry["asset"]
            timeframe = entry["timeframe"]

            try:
                series = await self._client.fetch_series(slug)
                series_id = series.series_id if series else None

                events = await self._client.fetch_events(slug, limit=20)

                async with factory() as session:
                    upserted_this_series = 0
                    for event in events:
                        for market in event.markets:
                            status = _determine_status(
                                is_active=market.is_active,
                                is_closed=market.is_closed,
                                start_time=market.start_time,
                                end_time=market.end_time,
                            )
                            await upsert_universe_market(
                                session,
                                asset=asset,
                                timeframe=timeframe,
                                series_slug=slug,
                                series_id=series_id,
                                event_id=event.event_id,
                                condition_id=market.condition_id,
                                yes_token_id=market.yes_token_id,
                                no_token_id=market.no_token_id,
                                question=market.question or event.title,
                                start_time=market.start_time or event.start_time,
                                end_time=market.end_time or event.end_time,
                                status=status,
                            )
                            upserted_this_series += 1

                    expired = await expire_stale_markets(session)
                    await session.commit()

                    total_upserted += upserted_this_series
                    total_expired_by_time += expired

                    logger.debug(
                        "Series synced",
                        slug=slug,
                        upserted=upserted_this_series,
                        stale_expired=expired,
                    )

            except Exception as exc:
                msg = f"{slug}: {exc}"
                errors.append(msg)
                logger.error("Series sync failed", slug=slug, error=str(exc))

        elapsed_ms = (
            datetime.now(timezone.utc) - started_at
        ).total_seconds() * 1000
        self._last_sync = datetime.now(timezone.utc)
        self._last_sync_duration_ms = elapsed_ms

        summary = {
            "synced_at": self._last_sync.isoformat(),
            "duration_ms": round(elapsed_ms, 1),
            "series_processed": len(SERIES_CATALOG),
            "markets_upserted": total_upserted,
            "markets_expired_by_time": total_expired_by_time,
            "errors": errors,
        }

        logger.info(
            "Universe sync complete",
            duration_ms=round(elapsed_ms, 1),
            markets_upserted=total_upserted,
            errors=len(errors),
        )
        return summary

    async def close(self) -> None:
        await self._client.close()

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    @property
    def last_sync_duration_ms(self) -> Optional[float]:
        return self._last_sync_duration_ms
