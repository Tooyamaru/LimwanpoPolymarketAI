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
from app.workers.engine_workers import (
    run_execution_engine_loop,
    run_exit_engine_loop,
    run_opportunity_engine_loop,
    run_position_tracking_loop,
    run_price_refresh_loop,
    run_risk_engine_loop,
    run_signal_engine_loop,
    run_strategy_engine_loop,
    run_universe_sync_loop,
)

import app.models  # noqa: F401  — registers all ORM models before init_db()

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

    # DEF-002 fix: gate that downstream engines wait on before their first
    # cycle.  Set by universe sync after its startup run completes so that
    # market_universe already contains the current active condition IDs.
    universe_ready_event: asyncio.Event | None = None
    if settings.UNIVERSE_SYNC_ENABLED and settings.PRICE_REFRESH_ENABLED:
        universe_ready_event = asyncio.Event()

    # ── Universe sync (every 60 s) ────────────────────────────────────────────
    universe_task = None
    if settings.UNIVERSE_SYNC_ENABLED:
        from app.services.market_universe_service import MarketUniverseService
        universe_service = MarketUniverseService()
        universe_task = asyncio.create_task(
            run_universe_sync_loop(universe_service, universe_ready=universe_ready_event)
        )
        app.state.universe_service = universe_service
        logger.info(
            "Universe sync started",
            interval=settings.UNIVERSE_SYNC_INTERVAL_SECONDS,
            run_on_startup=settings.UNIVERSE_SYNC_RUN_ON_STARTUP,
        )

    # ── Price refresh (every 10 s) ────────────────────────────────────────────
    price_task = None
    if settings.PRICE_REFRESH_ENABLED:
        from app.services.market_price_service import MarketPriceService
        price_service = MarketPriceService()
        price_task = asyncio.create_task(
            run_price_refresh_loop(price_service, universe_ready=universe_ready_event)
        )
        app.state.price_service = price_service
        logger.info(
            "Price refresh started",
            interval=settings.PRICE_REFRESH_SECONDS,
            run_on_startup=settings.PRICE_REFRESH_RUN_ON_STARTUP,
        )

    # ── Signal engine (every 10 s) — Layer 4 ─────────────────────────────────
    signal_task = None
    if settings.SIGNAL_ENGINE_ENABLED:
        from app.services.signal_engine import SignalEngine
        signal_engine = SignalEngine()
        signal_task = asyncio.create_task(
            run_signal_engine_loop(signal_engine, universe_ready=universe_ready_event)
        )
        app.state.signal_engine = signal_engine
        logger.info(
            "Signal engine started",
            interval=settings.SIGNAL_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.SIGNAL_ENGINE_RUN_ON_STARTUP,
        )

    # ── Opportunity engine (every 30 s) — Layer 5 ────────────────────────────
    opportunity_task = None
    if settings.OPPORTUNITY_ENGINE_ENABLED:
        from app.services.opportunity_engine import OpportunityEngine
        opp_engine = OpportunityEngine()
        opportunity_task = asyncio.create_task(
            run_opportunity_engine_loop(opp_engine, universe_ready=universe_ready_event)
        )
        app.state.opportunity_engine = opp_engine
        logger.info(
            "Opportunity engine started",
            interval=settings.OPPORTUNITY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.OPPORTUNITY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Exit engine (every 30 s) — Layer 11 ──────────────────────────────────
    exit_task = None
    if settings.EXIT_ENGINE_ENABLED:
        from app.services.exit_engine import ExitEngine
        exit_engine_instance = ExitEngine()
        exit_task = asyncio.create_task(
            run_exit_engine_loop(exit_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.exit_engine = exit_engine_instance
        logger.info(
            "Exit engine started",
            interval=settings.EXIT_ENGINE_INTERVAL_SECONDS,
        )

    # ── Strategy engine (every 60 s) — Layer 6 ───────────────────────────────
    strategy_task = None
    if settings.STRATEGY_ENGINE_ENABLED:
        from app.services.strategy_engine import StrategyEngine
        strat_engine = StrategyEngine()
        strategy_task = asyncio.create_task(
            run_strategy_engine_loop(strat_engine, universe_ready=universe_ready_event)
        )
        app.state.strategy_engine = strat_engine
        logger.info(
            "Strategy engine started",
            interval=settings.STRATEGY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.STRATEGY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Risk engine (every 15 s) — Layer 9 ───────────────────────────────────
    risk_task = None
    if settings.RISK_ENGINE_ENABLED:
        from app.services.risk_engine import RiskEngine
        risk_engine_instance = RiskEngine()
        risk_task = asyncio.create_task(
            run_risk_engine_loop(risk_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.risk_engine = risk_engine_instance
        logger.info(
            "Risk engine started",
            interval=settings.RISK_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.RISK_ENGINE_RUN_ON_STARTUP,
        )

    # ── Execution engine (every 30 s) — Layer 7 ──────────────────────────────
    execution_task = None
    if settings.EXECUTION_ENGINE_ENABLED:
        from app.services.execution_engine import ExecutionEngine
        exec_engine = ExecutionEngine()
        execution_task = asyncio.create_task(
            run_execution_engine_loop(exec_engine, universe_ready=universe_ready_event)
        )
        app.state.execution_engine = exec_engine
        logger.info(
            "Execution engine started",
            interval=settings.EXECUTION_ENGINE_INTERVAL_SECONDS,
            paper_mode=settings.EXECUTION_PAPER_MODE,
            run_on_startup=settings.EXECUTION_ENGINE_RUN_ON_STARTUP,
        )

    # ── Position tracking (every 30 s) — Layer 8 ─────────────────────────────
    from app.services.position_service import PositionService
    pos_service = PositionService()
    position_task = asyncio.create_task(
        run_position_tracking_loop(pos_service, universe_ready=universe_ready_event)
    )
    app.state.position_service = pos_service
    logger.info(
        "Position tracking started",
        interval=settings.POSITION_TRACKING_INTERVAL_SECONDS,
    )

    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down Polymarket Quant Bot")

    for task, name in [
        (universe_task, "universe"),
        (price_task, "price"),
        (signal_task, "signal"),
        (opportunity_task, "opportunity"),
        (exit_task, "exit"),
        (strategy_task, "strategy"),
        (risk_task, "risk"),
        (execution_task, "execution"),
        (position_task, "position"),
    ]:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"{name} task stopped")

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
