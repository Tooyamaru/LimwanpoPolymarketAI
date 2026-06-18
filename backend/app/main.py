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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting up Polymarket Quant Bot",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    await init_db()

    # Start collector scheduler in the background
    scheduler_task = None
    if settings.COLLECTOR_ENABLED:
        from app.collector.scheduler import CollectorScheduler
        scheduler = CollectorScheduler()
        scheduler_task = asyncio.create_task(scheduler.run())
        app.state.scheduler = scheduler
        logger.info(
            "Collector scheduler started",
            interval=settings.COLLECTOR_INTERVAL_SECONDS,
        )

    yield

    # Graceful shutdown
    logger.info("Shutting down Polymarket Quant Bot")
    if scheduler_task is not None:
        app.state.scheduler.stop()
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await app.state.scheduler.close()

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
