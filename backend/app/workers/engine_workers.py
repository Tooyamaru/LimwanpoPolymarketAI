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
  4. engine_health.record_heartbeat() is called after every successful cycle
     so the watchdog and /health/detailed endpoint can observe liveness.
"""

import asyncio

from app.config.settings import settings
from app.core import engine_health
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Universe sync (Layer 3) ────────────────────────────────────────────────────

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
            engine_health.record_heartbeat("universe_sync")
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
            engine_health.record_heartbeat("universe_sync")
        except Exception as exc:
            logger.error("Universe sync periodic run failed", error=str(exc))


# ── Price refresh (Layer 3b) ───────────────────────────────────────────────────

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
            engine_health.record_heartbeat("price_refresh")
        except Exception as exc:
            logger.error("Price refresh startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.PRICE_REFRESH_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("price_refresh")
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
            engine_health.record_heartbeat("signal_engine")
        except Exception as exc:
            logger.error("Signal engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.SIGNAL_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("signal_engine")
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
            engine_health.record_heartbeat("opportunity_engine")
        except Exception as exc:
            logger.error("Opportunity engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.OPPORTUNITY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("opportunity_engine")
        except Exception as exc:
            logger.error("Opportunity engine periodic run failed", error=str(exc))


# ── Exit engine (Layer 11) ─────────────────────────────────────────────────────

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
        engine_health.record_heartbeat("exit_engine")
    except Exception as exc:
        logger.error("Exit engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.EXIT_CHECK_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("exit_engine")
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
            engine_health.record_heartbeat("strategy_engine")
        except Exception as exc:
            logger.error("Strategy engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.STRATEGY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("strategy_engine")
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
            engine_health.record_heartbeat("risk_engine")
        except Exception as exc:
            logger.error("Risk engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.RISK_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("risk_engine")
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
            engine_health.record_heartbeat("execution_engine")
        except Exception as exc:
            logger.error("Execution engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.EXECUTION_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("execution_engine")
        except Exception as exc:
            logger.error("Execution engine periodic run failed", error=str(exc))


# ── Momentum engine (Decision Engine pipeline, stage 2) ───────────────────────

async def run_momentum_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Momentum engine background loop.

    Scores ROC/RSI/EMA-crossover momentum for every active asset/timeframe
    pair every MOMENTUM_ENGINE_INTERVAL_SECONDS (default 60 s). Read-only
    with respect to market data — only fetches public Binance klines.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.MOMENTUM_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("momentum_engine")
        except Exception as exc:
            logger.error("Momentum engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.MOMENTUM_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("momentum_engine")
        except Exception as exc:
            logger.error("Momentum engine periodic run failed", error=str(exc))


# ── Trend engine (Decision Engine pipeline, stage 3) ───────────────────────────

async def run_trend_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Trend engine background loop.

    Scores MACD/EMA-slope trend for every active asset/timeframe pair
    every TREND_ENGINE_INTERVAL_SECONDS (default 60 s). Read-only with
    respect to market data — only fetches public Binance klines.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.TREND_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("trend_engine")
        except Exception as exc:
            logger.error("Trend engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.TREND_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("trend_engine")
        except Exception as exc:
            logger.error("Trend engine periodic run failed", error=str(exc))


# ── Volatility engine (Decision Engine pipeline, stage 4) ─────────────────────

async def run_volatility_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Volatility engine background loop.

    Scores ATR-based tradability regime for every active asset/timeframe
    pair every VOLATILITY_ENGINE_INTERVAL_SECONDS (default 60 s). Read-only
    with respect to market data — only fetches public Binance klines.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.VOLATILITY_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("volatility_engine")
        except Exception as exc:
            logger.error("Volatility engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.VOLATILITY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("volatility_engine")
        except Exception as exc:
            logger.error("Volatility engine periodic run failed", error=str(exc))


# ── Decision engine (Decision Engine pipeline, final stage) ───────────────────

async def run_decision_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Decision engine background loop.

    Combines Signal, Momentum, Trend, Volatility, Opportunity, and a
    read-only Risk context into a BUY_YES / BUY_NO / WAIT verdict per
    active market every DECISION_ENGINE_INTERVAL_SECONDS (default 60 s).
    Runs last in the pipeline so upstream engines have already cycled.
    Read-only: never mutates market_universe, positions, orders, or
    trade_decisions — only appends to decision_logs.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.decide(session)

    if settings.DECISION_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("decision_engine")
        except Exception as exc:
            logger.error("Decision engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.DECISION_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("decision_engine")
        except Exception as exc:
            logger.error("Decision engine periodic run failed", error=str(exc))


# ── Market Quality engine (Phase Next — PRIMARY gate) ──────────────────────────

async def run_market_quality_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Polymarket Market Engine background loop.

    Scores GOOD/AVERAGE/BAD market tradability from Polymarket's own bid/ask,
    spread, liquidity, volume, and countdown-to-expiry data every
    MARKET_QUALITY_ENGINE_INTERVAL_SECONDS (default 30 s). This is the
    PRIMARY gate the Decision Engine reads first — it must run before
    Decision Engine's own cycle to have fresh data.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.MARKET_QUALITY_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("market_quality_engine")
        except Exception as exc:
            logger.error("Market quality engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.MARKET_QUALITY_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("market_quality_engine")
        except Exception as exc:
            logger.error("Market quality engine periodic run failed", error=str(exc))


# ── Market Context engine (Phase Next — supporting) ────────────────────────────

async def run_market_context_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Market Context Engine background loop.

    Checks whether an asset's active timeframes agree (ALIGNED/MIXED/CONFLICT)
    every MARKET_CONTEXT_ENGINE_INTERVAL_SECONDS (default 60 s). Reads the
    Momentum Engine's output, so should run after it has cycled at least once.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.MARKET_CONTEXT_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("market_context_engine")
        except Exception as exc:
            logger.error("Market context engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.MARKET_CONTEXT_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("market_context_engine")
        except Exception as exc:
            logger.error("Market context engine periodic run failed", error=str(exc))


# ── Orderbook engine (Phase Next — supporting) ─────────────────────────────────

async def run_orderbook_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Orderbook Engine background loop.

    Reads Binance spot order book depth for bid/ask imbalance every
    ORDERBOOK_ENGINE_INTERVAL_SECONDS (default 30 s). Read-only with respect
    to Polymarket data — confirmation signal only.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.ORDERBOOK_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("orderbook_engine")
        except Exception as exc:
            logger.error("Orderbook engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.ORDERBOOK_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("orderbook_engine")
        except Exception as exc:
            logger.error("Orderbook engine periodic run failed", error=str(exc))


# ── Funding engine (Phase Next — supporting) ───────────────────────────────────

async def run_funding_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Funding Engine background loop.

    Reads Binance perpetual futures funding rate / open interest / long-short
    ratio every FUNDING_ENGINE_INTERVAL_SECONDS (default 60 s). Read-only —
    confirmation signal only.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.FUNDING_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("funding_engine")
        except Exception as exc:
            logger.error("Funding engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.FUNDING_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("funding_engine")
        except Exception as exc:
            logger.error("Funding engine periodic run failed", error=str(exc))


# ── News engine (Phase Next — supporting, DEFERRED stub) ───────────────────────

async def run_news_engine_loop(
    engine,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    News Engine background loop (stub — deferred).

    Always writes NEUTRAL/confidence-0 rows every NEWS_ENGINE_INTERVAL_SECONDS
    (default 120 s) so the Decision Engine can already read a News row from
    day one. No external news/sentiment data source is wired up yet.
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await engine.scan(session)

    if settings.NEWS_ENGINE_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("news_engine")
        except Exception as exc:
            logger.error("News engine startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.NEWS_ENGINE_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("news_engine")
        except Exception as exc:
            logger.error("News engine periodic run failed", error=str(exc))


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
            engine_health.record_heartbeat("position_tracking")
        except Exception as exc:
            logger.error("Position tracking periodic run failed", error=str(exc))
        await asyncio.sleep(settings.POSITION_TRACKING_INTERVAL_SECONDS)


# ── Outcome Learning (Priority 1 + Priority 5) ────────────────────────────────

async def run_outcome_learning_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Outcome Learning background loop.

    Evaluates every expired Polymarket market against the last AI decision_log.
    Updates outcome_learnings and triggers engine performance recompute.
    Runs every OUTCOME_LEARNING_INTERVAL_SECONDS (default 300 s / 5 min).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await service.run(session)

    if settings.OUTCOME_LEARNING_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("outcome_learning")
            logger.info("Outcome learning startup run complete")
        except Exception as exc:
            logger.error("Outcome learning startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.OUTCOME_LEARNING_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("outcome_learning")
        except Exception as exc:
            logger.error("Outcome learning periodic run failed", error=str(exc))


# ── Dynamic Engine Weight (Priority 3) ────────────────────────────────────────

async def run_dynamic_weight_loop(
    service,
    universe_ready: asyncio.Event | None = None,
) -> None:
    """
    Dynamic Weight background loop.

    Reads EnginePerformance stats and recomputes adjusted engine weights.
    Runs every DYNAMIC_WEIGHT_INTERVAL_SECONDS (default 1800 s / 30 min).
    Startup run is disabled by default (no outcomes exist on first startup).
    """
    async def _one_cycle():
        from app.core.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await service.run(session)

    if settings.DYNAMIC_WEIGHT_RUN_ON_STARTUP:
        if universe_ready is not None:
            await universe_ready.wait()
        try:
            await _one_cycle()
            engine_health.record_heartbeat("dynamic_weight")
            logger.info("Dynamic weight startup run complete")
        except Exception as exc:
            logger.error("Dynamic weight startup run failed", error=str(exc))

    while True:
        await asyncio.sleep(settings.DYNAMIC_WEIGHT_INTERVAL_SECONDS)
        try:
            await _one_cycle()
            engine_health.record_heartbeat("dynamic_weight")
        except Exception as exc:
            logger.error("Dynamic weight periodic run failed", error=str(exc))
