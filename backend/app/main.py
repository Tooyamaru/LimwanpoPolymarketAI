import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config.settings import settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis

# Import models so their tables are registered with Base.metadata before init_db()
import app.models  # noqa: F401

setup_logging()
logger = get_logger(__name__)


async def _run_scanner_loop(scanner) -> None:
    """
    Scanner background loop.

    Optionally runs once on startup, then repeats every SCANNER_INTERVAL_SECONDS.
    Discovery paginates ~20k Polymarket markets so the interval is much longer
    than the price-collection tick (default 300 s vs 5 s).
    """
    if settings.SCANNER_RUN_ON_STARTUP:
        try:
            await scanner.run()
        except Exception as exc:
            logger.error("Scanner startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.SCANNER_INTERVAL_SECONDS)
        try:
            await scanner.run()
        except Exception as exc:
            logger.error("Scanner periodic run failed", error=str(exc))


async def _run_price_refresh_loop(service) -> None:
    """
    Price refresh background loop — Sprint 9.

    Optionally runs once on startup, then repeats every
    PRICE_REFRESH_SECONDS (default 10 s).
    Fetches live CLOB bid/ask for all active universe markets.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await service.refresh(session)

    if settings.PRICE_REFRESH_RUN_ON_STARTUP:
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Price refresh startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.PRICE_REFRESH_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Price refresh periodic run failed", error=str(exc))


async def _run_universe_sync_loop(service) -> None:
    """
    Universe sync background loop — Sprint 7.

    Optionally runs once on startup, then repeats every
    UNIVERSE_SYNC_INTERVAL_SECONDS (default 60 s).
    Only syncs known series — no large-scale market scanning.
    """
    if settings.UNIVERSE_SYNC_RUN_ON_STARTUP:
        try:
            await service.sync()
        except Exception as exc:
            logger.error("Universe sync startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.UNIVERSE_SYNC_INTERVAL_SECONDS)
        try:
            await service.sync()
        except Exception as exc:
            logger.error("Universe sync periodic run failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting up Polymarket Quant Bot",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    await init_db()

    # ── Price collector (every 5 s) ───────────────────────────────────────────
    collector_task = None
    if settings.COLLECTOR_ENABLED:
        from app.collector.scheduler import CollectorScheduler
        scheduler = CollectorScheduler()
        collector_task = asyncio.create_task(scheduler.run())
        app.state.collector = scheduler
        logger.info(
            "Price collector started",
            interval=settings.COLLECTOR_INTERVAL_SECONDS,
        )

    # ── Market scanner (every 300 s) ──────────────────────────────────────────
    scanner_task = None
    if settings.SCANNER_ENABLED:
        from app.services.scanner import ScannerService
        scanner = ScannerService()
        scanner_task = asyncio.create_task(_run_scanner_loop(scanner))
        app.state.scanner = scanner
        logger.info(
            "Market scanner started",
            interval=settings.SCANNER_INTERVAL_SECONDS,
            run_on_startup=settings.SCANNER_RUN_ON_STARTUP,
        )

    # ── Universe sync (every 60 s) — Sprint 7 ────────────────────────────────
    universe_task = None
    if settings.UNIVERSE_SYNC_ENABLED:
        from app.services.market_universe_service import MarketUniverseService
        universe_service = MarketUniverseService()
        universe_task = asyncio.create_task(_run_universe_sync_loop(universe_service))
        app.state.universe_service = universe_service
        logger.info(
            "Universe sync started",
            interval=settings.UNIVERSE_SYNC_INTERVAL_SECONDS,
            run_on_startup=settings.UNIVERSE_SYNC_RUN_ON_STARTUP,
        )

    # ── Price refresh (every 10 s) — Sprint 9 ────────────────────────────────
    price_task = None
    if settings.PRICE_REFRESH_ENABLED:
        from app.services.market_price_service import MarketPriceService
        price_service = MarketPriceService()
        price_task = asyncio.create_task(_run_price_refresh_loop(price_service))
        app.state.price_service = price_service
        logger.info(
            "Price refresh started",
            interval=settings.PRICE_REFRESH_SECONDS,
            run_on_startup=settings.PRICE_REFRESH_RUN_ON_STARTUP,
        )

    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down Polymarket Quant Bot")

    for task, name in [
        (collector_task, "collector"),
        (scanner_task, "scanner"),
        (universe_task, "universe"),
        (price_task, "price"),
    ]:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"{name} task stopped")

    if settings.COLLECTOR_ENABLED and hasattr(app.state, "collector"):
        app.state.collector.stop()
        await app.state.collector.close()

    if settings.SCANNER_ENABLED and hasattr(app.state, "scanner"):
        await app.state.scanner.close()

    if settings.UNIVERSE_SYNC_ENABLED and hasattr(app.state, "universe_service"):
        await app.state.universe_service.close()

    if settings.PRICE_REFRESH_ENABLED and hasattr(app.state, "price_service"):
        await app.state.price_service.close()

    await close_db()
    await close_redis()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
