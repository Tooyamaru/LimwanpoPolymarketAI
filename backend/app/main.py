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

    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down Polymarket Quant Bot")

    for task, name in [(collector_task, "collector"), (scanner_task, "scanner")]:
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
