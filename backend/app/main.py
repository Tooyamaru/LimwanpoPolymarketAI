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


async def _run_price_refresh_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Price refresh background loop — Sprint 9.

    Optionally runs once on startup, then repeats every
    PRICE_REFRESH_SECONDS (default 10 s).
    Fetches live CLOB bid/ask for all active universe markets.

    DEF-002 fix (Sprint 9.5): accepts an optional ``universe_ready`` event.
    When provided, the startup run is deferred until the event is set by
    ``_run_universe_sync_loop``, guaranteeing that the active-market list in
    ``market_universe`` is up-to-date before the first CLOB poll.  Without
    this gate, both tasks raced at startup and the price refresh queried stale
    condition IDs from the previous session, producing ``bid=0.01 /
    spread=0.98`` snapshots for the first ~2 minutes of every restart.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await service.refresh(session)

    if settings.PRICE_REFRESH_RUN_ON_STARTUP:
        if universe_ready is not None:
            logger.info("Price refresh waiting for first universe sync to complete")
            await universe_ready.wait()
            logger.info("Universe ready — price refresh startup cycle starting")
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


async def _run_execution_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Execution engine background loop — Layer 7.

    Runs every EXECUTION_ENGINE_INTERVAL_SECONDS (default 30 s).
    Processes PENDING OPEN_LONG_YES / OPEN_LONG_NO trade decisions and
    creates paper-mode Order fills.
    Gates on universe_ready so it starts only after the first universe sync.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await engine.run(session)

    if settings.EXECUTION_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Execution engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.EXECUTION_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Execution engine periodic run failed", error=str(exc))


async def _run_position_tracking_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Position tracking background loop — Layer 8.

    Runs every POSITION_TRACKING_INTERVAL_SECONDS (default 30 s).
    Creates positions from new FILLED orders, refreshes current_price
    from the opportunities table, and recomputes unrealized PnL.
    Gates on universe_ready so prices are available before first cycle.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await service.run(session)

    if universe_ready is not None:
        await universe_ready.wait()

    while True:
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Position tracking periodic run failed", error=str(exc))
        await asyncio.sleep(30)


async def _run_strategy_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Strategy engine background loop — Layer 6.

    Runs every STRATEGY_ENGINE_INTERVAL_SECONDS (default 60 s).
    Reads current Opportunity rows and emits TradeDecision records.
    Gates on universe_ready to ensure opportunities are populated first.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await engine.run(session)

    if settings.STRATEGY_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Strategy engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.STRATEGY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Strategy engine periodic run failed", error=str(exc))


async def _run_opportunity_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Opportunity engine background loop — Layer 5.

    Runs every OPPORTUNITY_ENGINE_INTERVAL_SECONDS (default 30 s).
    Evaluates all active markets and upserts their Opportunity Scores.
    Gates on universe_ready to ensure universe is populated first.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await engine.evaluate(session)

    if settings.OPPORTUNITY_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Opportunity engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.OPPORTUNITY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Opportunity engine periodic run failed", error=str(exc))


async def _run_signal_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Signal engine background loop — Layer 4.

    Runs every SIGNAL_ENGINE_INTERVAL_SECONDS (default 10 s).
    Compares consecutive price snapshots and emits signals to the DB.
    Gates on universe_ready so it starts after the first universe sync.
    """
    from app.core.database import get_session_factory

    async def _one_cycle():
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.SIGNAL_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Signal engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.SIGNAL_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Signal engine periodic run failed", error=str(exc))


async def _run_universe_sync_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Universe sync background loop — Sprint 7.

    Optionally runs once on startup, then repeats every
    UNIVERSE_SYNC_INTERVAL_SECONDS (default 60 s).
    Only syncs known series — no large-scale market scanning.

    DEF-002 fix (Sprint 9.5): accepts an optional ``universe_ready`` event
    that is set after the first sync attempt completes (success *or* error).
    This unblocks ``_run_price_refresh_loop`` so it only polls the CLOB
    after ``market_universe`` reflects the current active markets.  The event
    is set even on error so price refresh is never left hanging.
    """
    if settings.UNIVERSE_SYNC_RUN_ON_STARTUP:
        try:
            await service.sync()
            logger.info("Universe sync startup complete")
        except Exception as exc:
            logger.error("Universe sync startup run failed", error=str(exc))
        finally:
            if universe_ready is not None:
                universe_ready.set()
                logger.info("Universe ready event set — downstream engines may proceed")
    else:
        # run_on_startup=False (e.g. overridden by env var).
        # DB already contains universe data from previous sessions so
        # downstream engines (price refresh, signal, opportunity) can
        # start immediately. Set the gate now so they are not blocked.
        if universe_ready is not None:
            universe_ready.set()
            logger.info(
                "Universe ready event set immediately (run_on_startup=False) "
                "— downstream engines proceeding with existing DB state"
            )

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

    # ── DEF-002 fix: gate that price refresh must wait on before its first
    # cycle.  Set by universe sync after its startup run completes so that
    # market_universe already contains the current active condition IDs.
    universe_ready_event: asyncio.Event | None = None
    if settings.UNIVERSE_SYNC_ENABLED and settings.PRICE_REFRESH_ENABLED:
        universe_ready_event = asyncio.Event()

    # ── Universe sync (every 60 s) — Sprint 7 ────────────────────────────────
    universe_task = None
    if settings.UNIVERSE_SYNC_ENABLED:
        from app.services.market_universe_service import MarketUniverseService
        universe_service = MarketUniverseService()
        universe_task = asyncio.create_task(
            _run_universe_sync_loop(universe_service, universe_ready=universe_ready_event)
        )
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
        price_task = asyncio.create_task(
            _run_price_refresh_loop(price_service, universe_ready=universe_ready_event)
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
            _run_signal_engine_loop(signal_engine, universe_ready=universe_ready_event)
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
            _run_opportunity_engine_loop(opp_engine, universe_ready=universe_ready_event)
        )
        app.state.opportunity_engine = opp_engine
        logger.info(
            "Opportunity engine started",
            interval=settings.OPPORTUNITY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.OPPORTUNITY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Execution engine (every 30 s) — Layer 7 ──────────────────────────────
    execution_task = None
    if settings.EXECUTION_ENGINE_ENABLED:
        from app.services.execution_engine import ExecutionEngine
        exec_engine = ExecutionEngine()
        execution_task = asyncio.create_task(
            _run_execution_engine_loop(exec_engine, universe_ready=universe_ready_event)
        )
        app.state.execution_engine = exec_engine
        logger.info(
            "Execution engine started",
            interval=settings.EXECUTION_ENGINE_INTERVAL_SECONDS,
            paper_mode=settings.EXECUTION_PAPER_MODE,
            run_on_startup=settings.EXECUTION_ENGINE_RUN_ON_STARTUP,
        )

    # ── Strategy engine (every 60 s) — Layer 6 ───────────────────────────────
    strategy_task = None
    if settings.STRATEGY_ENGINE_ENABLED:
        from app.services.strategy_engine import StrategyEngine
        strat_engine = StrategyEngine()
        strategy_task = asyncio.create_task(
            _run_strategy_engine_loop(strat_engine, universe_ready=universe_ready_event)
        )
        app.state.strategy_engine = strat_engine
        logger.info(
            "Strategy engine started",
            interval=settings.STRATEGY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.STRATEGY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Position tracking (every 30 s) — Layer 8 ─────────────────────────────
    position_task = None
    from app.services.position_service import PositionService
    pos_service = PositionService()
    position_task = asyncio.create_task(
        _run_position_tracking_loop(pos_service, universe_ready=universe_ready_event)
    )
    app.state.position_service = pos_service
    logger.info("Position tracking started", interval=30)

    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down Polymarket Quant Bot")

    for task, name in [
        (collector_task, "collector"),
        (scanner_task, "scanner"),
        (universe_task, "universe"),
        (price_task, "price"),
        (signal_task, "signal"),
        (opportunity_task, "opportunity"),
        (strategy_task, "strategy"),
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
