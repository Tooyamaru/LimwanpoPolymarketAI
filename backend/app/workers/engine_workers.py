"""
workers/engine_workers.py — Background loop coroutines for all engines.

Each coroutine receives a pre-instantiated service/engine and runs it
on a fixed interval.  They are started as asyncio Tasks inside the
FastAPI lifespan (main.py) and cancelled on graceful shutdown.

Pattern
-------
  1. Optional startup run (gated on universe_ready if provided).
  2. Infinite while-loop with asyncio.sleep between cycles.
  3. All exceptions are caught and logged so one bad cycle never kills the loop.
"""

import asyncio

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

async def _with_session(service_coro):
    """Run a coroutine that requires a DB session, creating one per call."""
    from app.core.database import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        await service_coro(session)


# ── Scanner (Layer 2) ──────────────────────────────────────────────────────────

async def run_scanner_loop(scanner) -> None:
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


# ── Universe sync (Layer 3 / Sprint 7) ────────────────────────────────────────

async def run_universe_sync_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Universe sync background loop.

    Optionally runs once on startup, then repeats every
    UNIVERSE_SYNC_INTERVAL_SECONDS (default 60 s).

    DEF-002 fix: sets universe_ready after the first sync attempt (success or
    error) so downstream engines are never left waiting indefinitely.
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


# ── Price refresh (Layer 3 / Sprint 9) ────────────────────────────────────────

async def run_price_refresh_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Price refresh background loop.

    Fetches live CLOB bid/ask for all active universe markets every
    PRICE_REFRESH_SECONDS (default 10 s).

    DEF-002 fix: defers the startup run until universe_ready is set so the
    active-market list is up-to-date before the first CLOB poll.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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


# ── Signal engine (Layer 4) ────────────────────────────────────────────────────

async def run_signal_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Signal engine background loop.

    Compares consecutive price snapshots and emits signals every
    SIGNAL_ENGINE_INTERVAL_SECONDS (default 10 s).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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


# ── Opportunity engine (Layer 5) ───────────────────────────────────────────────

async def run_opportunity_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Opportunity engine background loop.

    Evaluates all active markets and upserts Opportunity Scores every
    OPPORTUNITY_ENGINE_INTERVAL_SECONDS (default 30 s).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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


# ── Exit engine (between Opportunity and Strategy) ─────────────────────────────

async def run_exit_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Exit engine background loop.

    Evaluates all OPEN positions against exit triggers and emits
    CLOSE_POSITION TradeDecision rows every EXIT_ENGINE_INTERVAL_SECONDS
    (default 30 s).

    Runs after the Opportunity Engine (needs fresh bid prices) and before
    the Strategy Engine in the pipeline ordering.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.run(session)

    if universe_ready is not None:
        await universe_ready.wait()
    try:
        await _one_cycle()
    except Exception as exc:
        logger.error("Exit engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.EXIT_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Exit engine periodic run failed", error=str(exc))


# ── Strategy engine (Layer 6) ──────────────────────────────────────────────────

async def run_strategy_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Strategy engine background loop.

    Reads Opportunity rows and emits TradeDecision records every
    STRATEGY_ENGINE_INTERVAL_SECONDS (default 60 s).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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


# ── Risk engine (Layer 9) ──────────────────────────────────────────────────────

async def run_risk_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Risk engine background loop.

    Screens PENDING TradeDecisions against risk rules and marks them
    RISK_APPROVED or BLOCKED every RISK_ENGINE_INTERVAL_SECONDS (default 15 s).
    Runs between the Strategy Engine and the Execution Engine in the pipeline.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.evaluate(session)

    if settings.RISK_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Risk engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.RISK_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
        except Exception as exc:
            logger.error("Risk engine periodic run failed", error=str(exc))


# ── Execution engine (Layer 7) ─────────────────────────────────────────────────

async def run_execution_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Execution engine background loop.

    Processes RISK_APPROVED OPEN_LONG decisions and creates paper-mode
    Order fills every EXECUTION_ENGINE_INTERVAL_SECONDS (default 30 s).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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


# ── Position tracking (Layer 8) ────────────────────────────────────────────────

async def run_position_tracking_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Position tracking background loop.

    Creates positions from new FILLED orders, refreshes current_price,
    and recomputes unrealized PnL every 30 s.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
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
        await asyncio.sleep(settings.POSITION_TRACKING_INTERVAL_SECONDS)
