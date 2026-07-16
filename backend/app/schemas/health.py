"""
Health response schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class EngineStatusEntry(BaseModel):
    """Per-engine liveness status reported by /health/detailed."""

    # "alive"       — last cycle within WATCHDOG_STALL_SECONDS
    # "stalled"     — last cycle older than WATCHDOG_STALL_SECONDS
    # "not_started" — engine has never completed a cycle since startup
    status: str
    seconds_since_last_cycle: Optional[float]


class TradingMetricsHealth(BaseModel):
    """
    Live trading health metrics appended to DetailedHealthResponse (Phase 4 Part G).

    All values are read-only snapshots from the capital management service
    and position performance analytics.  Failures to load these metrics
    are silenced — the main health status is never degraded by metric fetch errors.
    """

    # ── Capital guard-rails ────────────────────────────────────────────────────
    capital_allowed: bool               # False when kill-switch is active
    kill_switch_reason: Optional[str]   # reason code when allowed=False
    daily_pnl_usdc: float
    weekly_pnl_usdc: float
    drawdown_percent: float
    consecutive_losses: int

    # ── Performance summary ────────────────────────────────────────────────────
    avg_hold_time_minutes: float        # across all closed positions
    avg_fee_usdc: float                 # avg total fee per closed trade
    avg_slippage_usdc: float            # always 0.0 in paper mode
    total_closed_trades: int
    win_rate: float                     # percentage


class LastEventsHealth(BaseModel):
    """
    Most-recent timestamp for each major engine event (Phase 4 Task 8).

    All fields are optional — None when the event has never occurred since
    the database was initialised (fresh deployment with no trades).
    Datetime values are UTC ISO-8601 strings when serialised by FastAPI.
    """

    # Signal engine — most recent signal emitted
    last_signal: Optional[datetime] = None

    # Opportunity engine — most recent opportunity score computed
    last_opportunity: Optional[datetime] = None

    # Strategy engine — most recent OPEN_LONG_* decision created
    last_strategy: Optional[datetime] = None

    # Execution engine — most recent decision that reached EXECUTED status
    last_execution: Optional[datetime] = None

    # Exit engine — most recent CLOSE_POSITION decision that reached EXECUTED
    last_exit: Optional[datetime] = None

    # Most recent closed position where realized_pnl > 0
    last_successful_trade: Optional[datetime] = None


class PipelineCountsHealth(BaseModel):
    """
    Real engine-output counts for the Prediction Pipeline panel.

    Each field is sourced directly from the table the responsible engine writes:
    - total_signals          → Signal Engine    (signals table)
    - total_opportunities    → Opportunity Engine (opportunities table)
    - total_strategy_decisions → Strategy Engine (trade_decisions WHERE OPEN_LONG_*)
    - total_risk_evaluations → Risk Engine      (risk_events table)

    None means the DB was unreachable at the time of the health poll.
    """

    total_signals: int = 0              # Signal Engine: total signals detected
    total_opportunities: int = 0        # Opportunity Engine: total markets scored
    total_strategy_decisions: int = 0   # Strategy Engine: total OPEN_LONG decisions generated
    total_risk_evaluations: int = 0     # Risk Engine: total risk evaluations performed


class GammaIngestionHealth(BaseModel):
    """
    Gamma API ingestion status included in /health/detailed.

    status values:
      GAMMA_OK             — all configured series returned markets
      GAMMA_PARTIAL_SUCCESS — some series returned markets, others failed
      GAMMA_EMPTY_RESPONSE  — API reachable but all series returned 0 events
      GAMMA_UNREACHABLE     — all series failed with connection errors
      GAMMA_SSL_ERROR       — all series failed with TLS certificate errors
      UNKNOWN               — no sync has completed yet
    """
    status: str                        # classification string above
    market_universe_count: int         # current rows in market_universe table
    series_ok: int = 0                 # series that returned ≥1 market
    series_empty: int = 0              # series reachable but 0 events returned
    series_failed: int = 0             # series that raised an exception


class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    database: str
    redis: str
    engines: dict[str, EngineStatusEntry]

    # Phase 4 Part G — optional; None when DB is down or no trades yet
    trading_metrics: Optional[TradingMetricsHealth] = None

    # Phase 4 Task 8 — last-event timestamps; None when DB is down
    last_events: Optional[LastEventsHealth] = None

    # Phase 2 — pipeline queue counts; None when DB is down
    pipeline_counts: Optional[PipelineCountsHealth] = None

    # Gamma ingestion health — None when DB is unreachable
    gamma_ingestion: Optional[GammaIngestionHealth] = None
