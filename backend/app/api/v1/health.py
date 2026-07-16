"""
Health endpoints.
"""

import time as _time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core import engine_health
from app.core.database import check_db_health, get_db_session
from app.core.logging import get_logger
from app.core.redis import check_redis_health
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.models.signal import Signal
from app.models.trade_decision import TradeDecision
from app.schemas.health import (
    DetailedHealthResponse,
    EngineStatusEntry,
    GammaIngestionHealth,
    HealthResponse,
    LastEventsHealth,
    PipelineCountsHealth,
    TradingMetricsHealth,
)

logger = get_logger(__name__)
router = APIRouter()

_start_time: datetime = datetime.now(timezone.utc)

# In-memory cache for /health/detailed — 20s TTL.
# The dashboard polls every 30s; caching prevents 6+ redundant DB queries on
# any burst (multiple tabs open, health check tools, watchdog pings, etc.).
_HEALTH_CACHE_TTL: float = 20.0
_health_cache: dict = {"ts": 0.0, "data": None}


def get_uptime_seconds() -> float:
    return (datetime.now(timezone.utc) - _start_time).total_seconds()


@router.get("/health", response_model=HealthResponse, summary="Basic health check")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        uptime_seconds=get_uptime_seconds(),
    )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check with dependency, engine status, trading metrics, and last-event timestamps",
)
async def health_detailed(
    session: AsyncSession = Depends(get_db_session),
) -> DetailedHealthResponse:
    # Serve from cache if fresh enough (avoids 6+ DB queries per 30s poll)
    _now = _time.monotonic()
    if _health_cache["data"] is not None and _now - _health_cache["ts"] < _HEALTH_CACHE_TTL:
        return _health_cache["data"]

    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    # ── Engine liveness ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    stall_threshold = settings.WATCHDOG_STALL_SECONDS
    heartbeats = engine_health.get_heartbeats()
    registered = engine_health.get_registered()

    engines: dict[str, EngineStatusEntry] = {}
    any_stalled = False

    for name in registered:
        last_cycle = heartbeats.get(name)
        if last_cycle is None:
            engines[name] = EngineStatusEntry(
                status="not_started",
                seconds_since_last_cycle=None,
            )
        else:
            age = (now - last_cycle).total_seconds()
            if age > stall_threshold:
                status = "stalled"
                any_stalled = True
            else:
                status = "alive"
            engines[name] = EngineStatusEntry(
                status=status,
                seconds_since_last_cycle=round(age, 1),
            )

    # Scheduled batch engines with RUN_ON_STARTUP=False are intentionally
    # not_started until their first scheduled cycle arrives.  Counting them as
    # "overdue" produces a false-degraded overall status.  Realtime engines are
    # not in this set and remain subject to the overdue check as before.
    _SCHEDULED_ENGINES: frozenset[str] = frozenset({"dynamic_weight"})

    uptime = get_uptime_seconds()
    any_overdue_not_started = (
        any(
            e.status == "not_started"
            for name, e in engines.items()
            if name not in _SCHEDULED_ENGINES
        )
        and uptime > stall_threshold
    )
    overall = (
        "healthy"
        if (db_ok and not any_stalled and not any_overdue_not_started)
        else "degraded"
    )

    # ── Phase 4 Part G: trading metrics ───────────────────────────────────────
    trading_metrics: Optional[TradingMetricsHealth] = None
    if db_ok:
        try:
            trading_metrics = await _fetch_trading_metrics(session)
        except Exception as exc:
            logger.warning(
                "health_detailed: could not load trading metrics",
                error=str(exc),
            )

    # ── Phase 4 Task 8: last-event timestamps ─────────────────────────────────
    last_events: Optional[LastEventsHealth] = None
    if db_ok:
        try:
            last_events = await _fetch_last_event_timestamps(session)
        except Exception as exc:
            logger.warning(
                "health_detailed: could not load last-event timestamps",
                error=str(exc),
            )

    # ── Phase 2: pipeline queue counts ────────────────────────────────────────
    pipeline_counts: Optional[PipelineCountsHealth] = None
    if db_ok:
        try:
            pipeline_counts = await _fetch_pipeline_counts(session)
        except Exception as exc:
            logger.warning(
                "health_detailed: could not load pipeline counts",
                error=str(exc),
            )

    # ── Gamma ingestion health ─────────────────────────────────────────────────
    # If market_universe is empty after the startup window has elapsed,
    # Gamma ingestion is considered DEGRADED regardless of engine liveness.
    gamma_ingestion: Optional[GammaIngestionHealth] = None
    if db_ok:
        try:
            gamma_ingestion = await _fetch_gamma_ingestion_health(session, uptime)
            # Degrade overall status when Gamma ingestion is broken
            if gamma_ingestion.status not in ("GAMMA_OK", "GAMMA_PARTIAL_SUCCESS", "UNKNOWN"):
                overall = "degraded"
        except Exception as exc:
            logger.warning(
                "health_detailed: could not load gamma ingestion health",
                error=str(exc),
            )

    response = DetailedHealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        uptime_seconds=get_uptime_seconds(),
        database="healthy" if db_ok else "unhealthy",
        redis="healthy" if redis_ok else "unhealthy",
        engines=engines,
        trading_metrics=trading_metrics,
        last_events=last_events,
        pipeline_counts=pipeline_counts,
        gamma_ingestion=gamma_ingestion,
    )
    _health_cache["ts"] = _now
    _health_cache["data"] = response
    return response


async def _fetch_gamma_ingestion_health(
    session: AsyncSession,
    uptime_seconds: float,
) -> GammaIngestionHealth:
    """
    Report the live Gamma ingestion state from the market_universe table.

    Logic:
    - If uptime < 120s, the first sync may not have completed yet → UNKNOWN
    - If market_universe count > 0 → GAMMA_OK (data was ingested at some point)
    - If market_universe count == 0 and uptime >= 120s → ingestion is broken;
      the exact error code is unknown from the health endpoint alone, so
      we report GAMMA_UNREACHABLE (the sync endpoint provides finer detail)
    """
    from app.models.market_universe import MarketUniverse

    _STARTUP_GRACE_SECONDS = 120.0

    universe_count_res = await session.execute(
        select(func.count()).select_from(MarketUniverse)
    )
    universe_count = universe_count_res.scalar_one()

    if universe_count > 0:
        status = "GAMMA_OK"
    elif uptime_seconds < _STARTUP_GRACE_SECONDS:
        status = "UNKNOWN"
    else:
        status = "GAMMA_UNREACHABLE"

    return GammaIngestionHealth(
        status=status,
        market_universe_count=universe_count,
    )


async def _fetch_pipeline_counts(session: AsyncSession) -> PipelineCountsHealth:
    """
    Return real engine-output counts for the Prediction Pipeline panel.

    Each query targets the table owned by the responsible engine:
    - Signal Engine     → signals table (total rows)
    - Opportunity Engine → opportunities table (total rows)
    - Strategy Engine   → trade_decisions WHERE decision IN (OPEN_LONG_YES/NO)
    - Risk Engine       → risk_events table (total rows)

    All are fast COUNT(*) aggregates — each is a single index scan.
    """
    from app.models.risk_event import RiskEvent
    from app.models.signal import Signal
    from app.models.opportunity import Opportunity
    from app.models.trade_decision import TradeDecision

    sig_res = await session.execute(
        select(func.count()).select_from(Signal)
    )
    total_signals = sig_res.scalar_one()

    opp_res = await session.execute(
        select(func.count()).select_from(Opportunity)
    )
    total_opportunities = opp_res.scalar_one()

    strat_res = await session.execute(
        select(func.count()).select_from(TradeDecision).where(
            TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"])
        )
    )
    total_strategy_decisions = strat_res.scalar_one()

    risk_res = await session.execute(
        select(func.count()).select_from(RiskEvent)
    )
    total_risk_evaluations = risk_res.scalar_one()

    return PipelineCountsHealth(
        total_signals=total_signals,
        total_opportunities=total_opportunities,
        total_strategy_decisions=total_strategy_decisions,
        total_risk_evaluations=total_risk_evaluations,
    )


async def _fetch_trading_metrics(session: AsyncSession) -> TradingMetricsHealth:
    """
    Pull capital-management and performance-analytics snapshots to populate
    the TradingMetricsHealth block.
    """
    from app.services.capital_management_service import CapitalManagementService
    from app.services.performance_analytics_service import PerformanceAnalyticsService

    capital_svc = CapitalManagementService()
    perf_svc = PerformanceAnalyticsService()

    capital = await capital_svc.evaluate(session)
    perf = await perf_svc.get_performance_analytics(session)

    return TradingMetricsHealth(
        capital_allowed=capital.allowed,
        kill_switch_reason=capital.reason,
        daily_pnl_usdc=capital.daily_pnl,
        weekly_pnl_usdc=capital.weekly_pnl,
        drawdown_percent=capital.drawdown_percent,
        consecutive_losses=capital.consecutive_losses,
        avg_hold_time_minutes=perf.get("avg_hold_time_minutes", 0.0),
        avg_fee_usdc=perf.get("avg_fee_usdc", 0.0),
        avg_slippage_usdc=0.0,
        total_closed_trades=perf.get("total_trades", 0),
        win_rate=perf.get("win_rate", 0.0),
    )


async def _fetch_last_event_timestamps(session: AsyncSession) -> LastEventsHealth:
    """
    Query the most-recent timestamp for each major pipeline event.

    All queries use MAX() aggregates — single fast index scan each.
    NULL is returned for any event that has never occurred.
    """

    # last_signal — most recent Signal detected
    sig_res = await session.execute(
        select(func.max(Signal.detected_at))
    )
    last_signal = sig_res.scalar_one_or_none()

    # last_opportunity — most recent Opportunity score computed
    opp_res = await session.execute(
        select(func.max(Opportunity.evaluated_at))
    )
    last_opportunity = opp_res.scalar_one_or_none()

    # last_strategy — most recent OPEN_LONG_* TradeDecision created
    strat_res = await session.execute(
        select(func.max(TradeDecision.decided_at)).where(
            TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"])
        )
    )
    last_strategy = strat_res.scalar_one_or_none()

    # last_execution — most recent EXECUTED TradeDecision (any type)
    exec_res = await session.execute(
        select(func.max(TradeDecision.decided_at)).where(
            TradeDecision.status == "EXECUTED"
        )
    )
    last_execution = exec_res.scalar_one_or_none()

    # last_exit — most recent EXECUTED CLOSE_POSITION decision
    exit_res = await session.execute(
        select(func.max(TradeDecision.decided_at)).where(
            TradeDecision.decision == "CLOSE_POSITION",
            TradeDecision.status == "EXECUTED",
        )
    )
    last_exit = exit_res.scalar_one_or_none()

    # last_successful_trade — most recent Position closed with realized_pnl > 0
    trade_res = await session.execute(
        select(func.max(Position.closed_at)).where(
            Position.status == "CLOSED",
            Position.realized_pnl > 0,
        )
    )
    last_successful_trade = trade_res.scalar_one_or_none()

    return LastEventsHealth(
        last_signal=last_signal,
        last_opportunity=last_opportunity,
        last_strategy=last_strategy,
        last_execution=last_execution,
        last_exit=last_exit,
        last_successful_trade=last_successful_trade,
    )
