import asyncio
import sys  # noqa: F401 — used by watchdog via sys.exit
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.config.settings import settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis
from app.workers.engine_workers import (
    run_chainlink_loop,
    run_decision_engine_loop,
    run_dynamic_weight_loop,
    run_execution_engine_loop,
    run_exit_engine_loop,
    run_funding_engine_loop,
    run_market_context_engine_loop,
    run_market_quality_engine_loop,
    run_momentum_engine_loop,
    run_news_engine_loop,
    run_opportunity_engine_loop,
    run_orderbook_engine_loop,
    run_outcome_learning_loop,
    run_position_tracking_loop,
    run_price_refresh_loop,
    run_risk_engine_loop,
    run_signal_engine_loop,
    run_strategy_engine_loop,
    run_target_worker_loop,
    run_trend_engine_loop,
    run_universe_sync_loop,
    run_volatility_engine_loop,
)
from app.workers.watchdog import run_watchdog_loop

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

    # ── Chainlink RTDS client (singleton — started before all engines) ────────
    # The client connects to wss://ws-live-data.polymarket.com and subscribes
    # to live Chainlink oracle prices. Started first so prices are available
    # by the time the strategy engine needs them for the integrity gate.
    chainlink_task = None
    if settings.CHAINLINK_ENABLED:
        from app.services.chainlink_client import ChainlinkRTDSClient, set_chainlink_client
        _chainlink_client = ChainlinkRTDSClient()
        set_chainlink_client(_chainlink_client)
        chainlink_task = asyncio.create_task(
            run_chainlink_loop(_chainlink_client)
        )
        app.state.chainlink_client = _chainlink_client
        logger.info(
            "Chainlink RTDS client started",
            url=settings.CHAINLINK_WS_URL,
            topic=settings.CHAINLINK_TOPIC,
            integrity_gate=settings.CHAINLINK_INTEGRITY_GATE_ENABLED,
        )

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

    # ── Momentum engine (every 60 s) — Decision Engine pipeline stage 2 ─────
    momentum_task = None
    if settings.MOMENTUM_ENGINE_ENABLED:
        from app.services.momentum_engine import MomentumEngine
        momentum_engine_instance = MomentumEngine()
        momentum_task = asyncio.create_task(
            run_momentum_engine_loop(momentum_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.momentum_engine = momentum_engine_instance
        logger.info(
            "Momentum engine started",
            interval=settings.MOMENTUM_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.MOMENTUM_ENGINE_RUN_ON_STARTUP,
        )

    # ── Trend engine (every 60 s) — Decision Engine pipeline stage 3 ────────
    trend_task = None
    if settings.TREND_ENGINE_ENABLED:
        from app.services.trend_engine import TrendEngine
        trend_engine_instance = TrendEngine()
        trend_task = asyncio.create_task(
            run_trend_engine_loop(trend_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.trend_engine = trend_engine_instance
        logger.info(
            "Trend engine started",
            interval=settings.TREND_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.TREND_ENGINE_RUN_ON_STARTUP,
        )

    # ── Volatility engine (every 60 s) — Decision Engine pipeline stage 4 ───
    volatility_task = None
    if settings.VOLATILITY_ENGINE_ENABLED:
        from app.services.volatility_engine import VolatilityEngine
        volatility_engine_instance = VolatilityEngine()
        volatility_task = asyncio.create_task(
            run_volatility_engine_loop(volatility_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.volatility_engine = volatility_engine_instance
        logger.info(
            "Volatility engine started",
            interval=settings.VOLATILITY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.VOLATILITY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Market Quality engine (every 30 s) — Phase Next PRIMARY gate ────────
    # Polymarket's own bid/ask/spread/liquidity/volume/expiry is the source
    # of truth. Started before Decision Engine so it always has fresh data.
    market_quality_task = None
    if settings.MARKET_QUALITY_ENGINE_ENABLED:
        from app.services.polymarket_market_engine import PolymarketMarketEngine
        market_quality_engine_instance = PolymarketMarketEngine()
        market_quality_task = asyncio.create_task(
            run_market_quality_engine_loop(market_quality_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.market_quality_engine = market_quality_engine_instance
        logger.info(
            "Market quality engine started",
            interval=settings.MARKET_QUALITY_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.MARKET_QUALITY_ENGINE_RUN_ON_STARTUP,
        )

    # ── Market Context engine (every 60 s) — Phase Next supporting ─────────
    market_context_task = None
    if settings.MARKET_CONTEXT_ENGINE_ENABLED:
        from app.services.market_context_engine import MarketContextEngine
        market_context_engine_instance = MarketContextEngine()
        market_context_task = asyncio.create_task(
            run_market_context_engine_loop(market_context_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.market_context_engine = market_context_engine_instance
        logger.info(
            "Market context engine started",
            interval=settings.MARKET_CONTEXT_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.MARKET_CONTEXT_ENGINE_RUN_ON_STARTUP,
        )

    # ── Orderbook engine (every 30 s) — Phase Next supporting ───────────────
    orderbook_task = None
    if settings.ORDERBOOK_ENGINE_ENABLED:
        from app.services.orderbook_engine import OrderbookEngine
        orderbook_engine_instance = OrderbookEngine()
        orderbook_task = asyncio.create_task(
            run_orderbook_engine_loop(orderbook_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.orderbook_engine = orderbook_engine_instance
        logger.info(
            "Orderbook engine started",
            interval=settings.ORDERBOOK_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.ORDERBOOK_ENGINE_RUN_ON_STARTUP,
        )

    # ── Funding engine (every 60 s) — Phase Next supporting ─────────────────
    funding_task = None
    if settings.FUNDING_ENGINE_ENABLED:
        from app.services.funding_engine import FundingEngine
        funding_engine_instance = FundingEngine()
        funding_task = asyncio.create_task(
            run_funding_engine_loop(funding_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.funding_engine = funding_engine_instance
        logger.info(
            "Funding engine started",
            interval=settings.FUNDING_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.FUNDING_ENGINE_RUN_ON_STARTUP,
        )

    # ── News engine (every 120 s) — Phase Next supporting, DEFERRED stub ────
    news_task = None
    if settings.NEWS_ENGINE_ENABLED:
        from app.services.news_engine import NewsEngine
        news_engine_instance = NewsEngine()
        news_task = asyncio.create_task(
            run_news_engine_loop(news_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.news_engine = news_engine_instance
        logger.info(
            "News engine started (stub — deferred)",
            interval=settings.NEWS_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.NEWS_ENGINE_RUN_ON_STARTUP,
        )

    # ── Decision engine (every 60 s) — Decision Engine pipeline final stage ─
    # Runs read-only: never mutates market_universe/positions/orders, only
    # appends to decision_logs. Deliberately started after the engines it
    # reads from (signal/momentum/trend/volatility/opportunity/market
    # quality/market context/orderbook/funding/news).
    decision_task = None
    if settings.DECISION_ENGINE_ENABLED:
        from app.services.decision_engine import DecisionEngine
        decision_engine_instance = DecisionEngine()
        decision_task = asyncio.create_task(
            run_decision_engine_loop(decision_engine_instance, universe_ready=universe_ready_event)
        )
        app.state.decision_engine = decision_engine_instance
        logger.info(
            "Decision engine started",
            interval=settings.DECISION_ENGINE_INTERVAL_SECONDS,
            run_on_startup=settings.DECISION_ENGINE_RUN_ON_STARTUP,
        )

    # ── Outcome Learning (every 300 s) — Priority 1 + Priority 5 ────────────
    outcome_learning_task = None
    if settings.OUTCOME_LEARNING_ENABLED:
        from app.services.outcome_learning_service import OutcomeLearningService
        outcome_learning_instance = OutcomeLearningService()
        outcome_learning_task = asyncio.create_task(
            run_outcome_learning_loop(outcome_learning_instance, universe_ready=universe_ready_event)
        )
        app.state.outcome_learning_service = outcome_learning_instance
        logger.info(
            "Outcome learning started",
            interval=settings.OUTCOME_LEARNING_INTERVAL_SECONDS,
            run_on_startup=settings.OUTCOME_LEARNING_RUN_ON_STARTUP,
        )

    # ── Dynamic Weight (every 1800 s) — Priority 3 ───────────────────────────
    dynamic_weight_task = None
    if settings.DYNAMIC_WEIGHT_ENABLED:
        from app.services.dynamic_weight_service import DynamicWeightService
        dynamic_weight_instance = DynamicWeightService()
        dynamic_weight_task = asyncio.create_task(
            run_dynamic_weight_loop(dynamic_weight_instance, universe_ready=universe_ready_event)
        )
        app.state.dynamic_weight_service = dynamic_weight_instance
        logger.info(
            "Dynamic weight engine started",
            interval=settings.DYNAMIC_WEIGHT_INTERVAL_SECONDS,
            run_on_startup=settings.DYNAMIC_WEIGHT_RUN_ON_STARTUP,
            min_outcomes=settings.DYNAMIC_WEIGHT_MIN_OUTCOMES,
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

    # ── Target worker (every 30 s) ────────────────────────────────────────────
    # Fetches the official Price to Beat from the Gamma API for each active
    # market that has not yet been verified.  Runs after universe_ready so
    # the market_universe table already contains the current condition IDs.
    target_worker_task = None
    if settings.TARGET_WORKER_ENABLED:
        from app.services.target_worker import TargetWorker
        _target_worker = TargetWorker()
        target_worker_task = asyncio.create_task(
            run_target_worker_loop(_target_worker, universe_ready=universe_ready_event)
        )
        app.state.target_worker = _target_worker
        logger.info(
            "Target worker started",
            interval=settings.TARGET_WORKER_INTERVAL_SECONDS,
        )

    # ── Engine registration — always runs regardless of WATCHDOG_ENABLED ────
    # registered_engines: every active engine, passed to engine_health so
    # /health/detailed can report all of them (including not_started).
    #
    # watchdog_engines: continuous realtime engines only — those whose natural
    # work cadence fits within WATCHDOG_RESTART_SECONDS.  Batch/scheduled
    # engines with long intervals (e.g. dynamic_weight at 1800 s) are excluded
    # so the watchdog does not kill the process waiting for a heartbeat that
    # will legitimately arrive much later.
    from app.core import engine_health as _engine_health
    registered_engines: list[str] = []
    if settings.UNIVERSE_SYNC_ENABLED:
        registered_engines.append("universe_sync")
    if settings.PRICE_REFRESH_ENABLED:
        registered_engines.append("price_refresh")
    if settings.SIGNAL_ENGINE_ENABLED:
        registered_engines.append("signal_engine")
    if settings.OPPORTUNITY_ENGINE_ENABLED:
        registered_engines.append("opportunity_engine")
    if settings.EXIT_ENGINE_ENABLED:
        registered_engines.append("exit_engine")
    if settings.STRATEGY_ENGINE_ENABLED:
        registered_engines.append("strategy_engine")
    if settings.RISK_ENGINE_ENABLED:
        registered_engines.append("risk_engine")
    if settings.EXECUTION_ENGINE_ENABLED:
        registered_engines.append("execution_engine")
    if settings.MOMENTUM_ENGINE_ENABLED:
        registered_engines.append("momentum_engine")
    if settings.TREND_ENGINE_ENABLED:
        registered_engines.append("trend_engine")
    if settings.VOLATILITY_ENGINE_ENABLED:
        registered_engines.append("volatility_engine")
    if settings.MARKET_QUALITY_ENGINE_ENABLED:
        registered_engines.append("market_quality_engine")
    if settings.MARKET_CONTEXT_ENGINE_ENABLED:
        registered_engines.append("market_context_engine")
    if settings.ORDERBOOK_ENGINE_ENABLED:
        registered_engines.append("orderbook_engine")
    if settings.FUNDING_ENGINE_ENABLED:
        registered_engines.append("funding_engine")
    if settings.NEWS_ENGINE_ENABLED:
        registered_engines.append("news_engine")
    if settings.DECISION_ENGINE_ENABLED:
        registered_engines.append("decision_engine")
    if settings.OUTCOME_LEARNING_ENABLED:
        registered_engines.append("outcome_learning")
    if settings.DYNAMIC_WEIGHT_ENABLED:
        registered_engines.append("dynamic_weight")  # health reporting only
    registered_engines.append("position_tracking")  # always on
    _engine_health.register_engines(registered_engines)

    # Watchdog monitors only continuous realtime engines.  dynamic_weight is a
    # scheduled batch worker (interval=1800 s) that intentionally has
    # RUN_ON_STARTUP=False; its natural cycle exceeds WATCHDOG_RESTART_SECONDS
    # (600 s) so it must not participate in restart decisions.
    watchdog_engines: list[str] = [
        e for e in registered_engines if e != "dynamic_weight"
    ]

    # ── Watchdog (every 60 s) — monitors engine heartbeats ───────────────────
    watchdog_task = None
    if settings.WATCHDOG_ENABLED:
        watchdog_task = asyncio.create_task(
            run_watchdog_loop(enabled_engines=watchdog_engines)
        )
        logger.info(
            "Watchdog started",
            monitored_engines=len(watchdog_engines),
            grace_seconds=settings.WATCHDOG_GRACE_SECONDS,
            stall_threshold=settings.WATCHDOG_STALL_SECONDS,
            restart_threshold=settings.WATCHDOG_RESTART_SECONDS,
        )

    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down Polymarket Quant Bot")

    for task, name in [
        (watchdog_task, "watchdog"),
        (chainlink_task, "chainlink"),
        (target_worker_task, "target_worker"),
        (universe_task, "universe"),
        (price_task, "price"),
        (signal_task, "signal"),
        (opportunity_task, "opportunity"),
        (exit_task, "exit"),
        (strategy_task, "strategy"),
        (risk_task, "risk"),
        (execution_task, "execution"),
        (momentum_task, "momentum"),
        (trend_task, "trend"),
        (volatility_task, "volatility"),
        (market_quality_task, "market_quality"),
        (market_context_task, "market_context"),
        (orderbook_task, "orderbook"),
        (funding_task, "funding"),
        (news_task, "news"),
        (decision_task, "decision"),
        (outcome_learning_task, "outcome_learning"),
        (dynamic_weight_task, "dynamic_weight"),
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

    # Dashboard — served from app/static/
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/static/index.html")

    return app


app = create_application()
