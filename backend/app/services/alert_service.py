"""
Alert Service — Phase 12: Monitoring / Alert / Operator Safety System.

Produces a read-only snapshot of operator-facing alerts derived exclusively
from real DB state, engine heartbeats (app.core.engine_health), and
already-configured settings thresholds. This service:

  - NEVER fabricates, hardcodes, or randomises an alert.
  - NEVER mutates the database, triggers a trade, or triggers execution.
  - NEVER silently downgrades a failed check to "OK". If a check's own query
    raises, that failure becomes a CRITICAL MONITORING_QUERY_FAILED alert
    naming the failed check, and the overall snapshot status is forced to
    at least WARNING (CRITICAL, since a query failure is itself critical —
    see AlertService.snapshot()).

Each _check_* method is independent and wrapped individually so one bad
query cannot silently hide the rest of the snapshot, and cannot be silently
swallowed into a false "OK" either.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core import engine_health
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.outcome_learning import OutcomeLearning
from app.models.position import Position
from app.models.trade_decision import TradeDecision

logger = get_logger(__name__)

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

# ── Thresholds (documented; not hidden magic numbers) ───────────────────────
# Reuses existing watchdog thresholds for engine/API liveness so this service
# does not invent a second, inconsistent definition of "stalled".
_ENGINE_WARN_SECONDS = settings.WATCHDOG_STALL_SECONDS
_ENGINE_CRIT_SECONDS = settings.WATCHDOG_RESTART_SECONDS

# Gamma is called only by universe_sync; CLOB is called only by price_refresh.
# Both engines record a heartbeat ONLY after their respective API call
# succeeds (see app/workers/engine_workers.py) — so heartbeat age is a real,
# non-fabricated proxy for upstream API health, not a fresh counter.
_GAMMA_WARN_SECONDS = max(_ENGINE_WARN_SECONDS, settings.UNIVERSE_SYNC_INTERVAL_SECONDS * 5)
_GAMMA_CRIT_SECONDS = max(_ENGINE_CRIT_SECONDS, settings.UNIVERSE_SYNC_INTERVAL_SECONDS * 10)
_CLOB_WARN_SECONDS = max(_ENGINE_WARN_SECONDS, settings.PRICE_REFRESH_SECONDS * 10)
_CLOB_CRIT_SECONDS = max(_ENGINE_CRIT_SECONDS, settings.PRICE_REFRESH_SECONDS * 20)

# A RISK_APPROVED decision should be picked up by the next Execution Engine
# cycle (EXECUTION_ENGINE_INTERVAL_SECONDS). If it is still RISK_APPROVED
# well beyond that, Execution is repeatedly failing on it — the closest real
# proxy available for "execution error spike", since TradeDecision has no
# FAILED status in the current schema.
_STUCK_RISK_APPROVED_WARN_MINUTES = 5.0
_STUCK_RISK_APPROVED_CRIT_MINUTES = 15.0

# A PENDING actionable decision (OPEN_LONG_YES/NO) should be evaluated by the
# next Risk Engine cycle (RISK_ENGINE_INTERVAL_SECONDS=15s by default). If it
# is still PENDING well beyond that, the risk gate itself is stuck — the
# closest real proxy available, since there is no "risk_gated" field in the
# current schema.
_RISK_GATE_STUCK_WARN_MINUTES = 5.0
_RISK_GATE_STUCK_CRIT_MINUTES = 15.0

# How long an expired market may go without a direct/proxy outcome resolution
# before it is flagged. Grace period covers the 5-minute Outcome Learning
# cycle interval plus a safety margin.
_DIRECT_RESOLUTION_WARN_MINUTES = 20.0
_DIRECT_RESOLUTION_CRIT_MINUTES = 90.0

# How long an expired OPEN position may exist without a CLOSE_POSITION
# decision before the forced-exit path is considered overdue.
_FORCED_EXIT_WARN_MINUTES = float(settings.EXIT_FORCE_EXPIRY_MINUTES) * 2
_FORCED_EXIT_CRIT_MINUTES = float(settings.EXIT_FORCE_EXPIRY_MINUTES) * 6


def _alert(
    code: str,
    severity: str,
    message: str,
    evidence: dict[str, Any],
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "recommended_action": recommended_action,
    }


class AlertService:
    """Builds a real-data-only alert snapshot for operator review."""

    async def snapshot(self, session: AsyncSession) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        checks: list[Callable[[AsyncSession, datetime], Coroutine[Any, Any, list[dict]]]] = [
            self._check_engine_stalled,
            self._check_gamma_api_degraded,
            self._check_clob_api_degraded,
            self._check_no_markets_active,
            self._check_expired_position_open,
            self._check_direct_resolution_missing,
            self._check_execution_error_spike,
            self._check_risk_gate_stuck,
            self._check_duplicate_execution,
            self._check_portfolio_exposure_high,
            self._check_paper_pnl_anomaly,
            self._check_forced_exit_pending,
        ]

        alerts: list[dict[str, Any]] = []
        for check in checks:
            try:
                alerts.extend(await check(session, now))
            except Exception as exc:
                logger.error(
                    "Alert check failed — reporting as MONITORING_QUERY_FAILED "
                    "rather than silently skipping",
                    check=check.__name__,
                    error=str(exc),
                )
                alerts.append(
                    _alert(
                        code="MONITORING_QUERY_FAILED",
                        severity="CRITICAL",
                        message=f"Alert check '{check.__name__}' raised an exception "
                        "and could not be evaluated. Monitoring for this area is "
                        "currently BLIND, not OK.",
                        evidence={"check": check.__name__, "error": str(exc)},
                        recommended_action=(
                            "Investigate the exception in application logs immediately. "
                            "Do not assume this area is healthy until the check succeeds."
                        ),
                    )
                )

        critical = sum(1 for a in alerts if a["severity"] == "CRITICAL")
        warning = sum(1 for a in alerts if a["severity"] == "WARNING")
        info = sum(1 for a in alerts if a["severity"] == "INFO")

        if critical > 0:
            status = "CRITICAL"
        elif warning > 0:
            status = "WARNING"
        else:
            status = "OK"

        alerts.sort(key=lambda a: (-SEVERITY_RANK[a["severity"]], a["code"]))

        return {
            "status": status,
            "generated_at": now,
            "alerts": alerts,
            "summary": {"critical": critical, "warning": warning, "info": info},
        }

    # ── 1. ENGINE_STALLED ────────────────────────────────────────────────────

    async def _check_engine_stalled(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        alerts: list[dict] = []
        registered = engine_health.get_registered()
        heartbeats = engine_health.get_heartbeats()

        for name in registered:
            last = heartbeats.get(name)
            if last is None:
                continue  # not_started is a separate, expected startup state
            age = (now - last).total_seconds()
            if age > _ENGINE_CRIT_SECONDS:
                alerts.append(
                    _alert(
                        code="ENGINE_STALLED",
                        severity="CRITICAL",
                        message=f"Engine '{name}' has not completed a cycle in "
                        f"{age:.0f}s (> {_ENGINE_CRIT_SECONDS}s restart threshold).",
                        evidence={
                            "engine": name,
                            "seconds_since_last_cycle": round(age, 1),
                            "threshold_seconds": _ENGINE_CRIT_SECONDS,
                        },
                        recommended_action=(
                            "Check workflow logs for this engine's loop; the watchdog "
                            "should force-restart the process shortly. If it does not, "
                            "restart the workflow manually."
                        ),
                    )
                )
            elif age > _ENGINE_WARN_SECONDS:
                alerts.append(
                    _alert(
                        code="ENGINE_STALLED",
                        severity="WARNING",
                        message=f"Engine '{name}' has not completed a cycle in "
                        f"{age:.0f}s (> {_ENGINE_WARN_SECONDS}s stall threshold).",
                        evidence={
                            "engine": name,
                            "seconds_since_last_cycle": round(age, 1),
                            "threshold_seconds": _ENGINE_WARN_SECONDS,
                        },
                        recommended_action="Monitor; escalates to CRITICAL if it persists.",
                    )
                )
        return alerts

    # ── 2/3. GAMMA_API_DEGRADED / CLOB_API_DEGRADED ─────────────────────────

    async def _check_gamma_api_degraded(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        return self._check_api_proxy(
            now,
            engine_name="universe_sync",
            code="GAMMA_API_DEGRADED",
            warn_seconds=_GAMMA_WARN_SECONDS,
            crit_seconds=_GAMMA_CRIT_SECONDS,
            api_label="Gamma (universe sync)",
        )

    async def _check_clob_api_degraded(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        return self._check_api_proxy(
            now,
            engine_name="price_refresh",
            code="CLOB_API_DEGRADED",
            warn_seconds=_CLOB_WARN_SECONDS,
            crit_seconds=_CLOB_CRIT_SECONDS,
            api_label="CLOB (price refresh)",
        )

    @staticmethod
    def _check_api_proxy(
        now: datetime,
        *,
        engine_name: str,
        code: str,
        warn_seconds: float,
        crit_seconds: float,
        api_label: str,
    ) -> list[dict]:
        last = engine_health.get_heartbeats().get(engine_name)
        if last is None:
            return []  # startup grace — covered by ENGINE_STALLED once overdue
        age = (now - last).total_seconds()
        if age > crit_seconds:
            severity = "CRITICAL"
        elif age > warn_seconds:
            severity = "WARNING"
        else:
            return []
        return [
            _alert(
                code=code,
                severity=severity,
                message=f"{api_label} has not returned a successful response in "
                f"{age:.0f}s — the '{engine_name}' loop only heartbeats after a "
                "successful call, so this reflects real repeated failures, not "
                "just a slow cycle.",
                evidence={
                    "proxy_engine": engine_name,
                    "seconds_since_last_success": round(age, 1),
                    "warn_threshold_seconds": warn_seconds,
                    "crit_threshold_seconds": crit_seconds,
                },
                recommended_action=(
                    f"Check application logs for '{engine_name}' error entries and "
                    "verify the upstream API is reachable (rate limiting, outage, "
                    "network)."
                ),
            )
        ]

    # ── 4. NO_MARKETS_ACTIVE ─────────────────────────────────────────────────

    async def _check_no_markets_active(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        result = await session.execute(
            select(func.count(MarketUniverse.id)).where(MarketUniverse.status == "active")
        )
        count = int(result.scalar_one() or 0)
        if count > 0:
            return []
        return [
            _alert(
                code="NO_MARKETS_ACTIVE",
                severity="CRITICAL",
                message="market_universe has zero rows with status='active'. "
                "No new decisions can be generated.",
                evidence={"active_market_count": 0},
                recommended_action=(
                    "Check universe_sync heartbeat/logs — either Gamma sync stopped "
                    "producing active markets or all series have gone quiet."
                ),
            )
        ]

    # ── 5. EXPIRED_POSITION_OPEN ─────────────────────────────────────────────

    async def _check_expired_position_open(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        result = await session.execute(
            select(Position.id, Position.condition_id, Position.asset, Position.timeframe, MarketUniverse.end_time)
            .join(MarketUniverse, MarketUniverse.condition_id == Position.condition_id)
            .where(Position.status == "OPEN", MarketUniverse.end_time < now)
        )
        rows = result.all()
        if not rows:
            return []
        return [
            _alert(
                code="EXPIRED_POSITION_OPEN",
                severity="CRITICAL",
                message=f"{len(rows)} OPEN position(s) reference a market whose "
                "end_time has already passed.",
                evidence={
                    "count": len(rows),
                    "positions": [
                        {
                            "position_id": r.id,
                            "condition_id": r.condition_id[:16],
                            "asset": r.asset,
                            "timeframe": r.timeframe,
                            "end_time": r.end_time.isoformat() if r.end_time else None,
                        }
                        for r in rows[:10]
                    ],
                },
                recommended_action=(
                    "Verify the Exit Engine is running and evaluating EXPIRY_EXIT; "
                    "check for a pending CLOSE_POSITION decision (see FORCED_EXIT_PENDING)."
                ),
            )
        ]

    # ── 6. DIRECT_RESOLUTION_MISSING ─────────────────────────────────────────

    async def _check_direct_resolution_missing(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        warn_cutoff = now - timedelta(minutes=_DIRECT_RESOLUTION_WARN_MINUTES)

        result = await session.execute(
            select(
                Position.condition_id,
                Position.asset,
                Position.timeframe,
                MarketUniverse.end_time,
                OutcomeLearning.outcome_source,
            )
            .join(MarketUniverse, MarketUniverse.condition_id == Position.condition_id)
            .outerjoin(
                OutcomeLearning, OutcomeLearning.condition_id == Position.condition_id
            )
            .where(
                MarketUniverse.end_time.is_not(None),
                MarketUniverse.end_time < warn_cutoff,
            )
        )
        rows = result.all()

        stale: list[Any] = []
        for r in rows:
            if r.outcome_source is None or r.outcome_source == "NOT_AVAILABLE":
                stale.append(r)

        if not stale:
            return []

        crit_cutoff = now - timedelta(minutes=_DIRECT_RESOLUTION_CRIT_MINUTES)
        critical_rows = [r for r in stale if r.end_time < crit_cutoff]
        severity = "CRITICAL" if critical_rows else "WARNING"

        return [
            _alert(
                code="DIRECT_RESOLUTION_MISSING",
                severity=severity,
                message=f"{len(stale)} traded, expired market(s) still have no "
                "direct/proxy outcome resolution after "
                f"{_DIRECT_RESOLUTION_WARN_MINUTES:.0f}+ minutes.",
                evidence={
                    "count": len(stale),
                    "critical_count": len(critical_rows),
                    "examples": [
                        {
                            "condition_id": r.condition_id[:16],
                            "asset": r.asset,
                            "timeframe": r.timeframe,
                            "end_time": r.end_time.isoformat(),
                            "outcome_source": r.outcome_source,
                        }
                        for r in stale[:10]
                    ],
                },
                recommended_action=(
                    "Check OutcomeLearningService cycle logs and Gamma resolution "
                    "lookup for these condition_ids; verify the 5-minute cycle is "
                    "actually running (OUTCOME_LEARNING_ENABLED)."
                ),
            )
        ]

    # ── 7. EXECUTION_ERROR_SPIKE (proxy: stuck RISK_APPROVED decisions) ─────

    async def _check_execution_error_spike(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        warn_cutoff = now - timedelta(minutes=_STUCK_RISK_APPROVED_WARN_MINUTES)
        result = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.status == "RISK_APPROVED",
                TradeDecision.decided_at < warn_cutoff,
            )
        )
        count = int(result.scalar_one() or 0)
        if count == 0:
            return []

        crit_cutoff = now - timedelta(minutes=_STUCK_RISK_APPROVED_CRIT_MINUTES)
        crit_result = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.status == "RISK_APPROVED",
                TradeDecision.decided_at < crit_cutoff,
            )
        )
        crit_count = int(crit_result.scalar_one() or 0)
        severity = "CRITICAL" if crit_count > 0 else "WARNING"

        return [
            _alert(
                code="EXECUTION_ERROR_SPIKE",
                severity=severity,
                message=f"{count} decision(s) have been RISK_APPROVED for more than "
                f"{_STUCK_RISK_APPROVED_WARN_MINUTES:.0f} minutes without reaching "
                "EXECUTED. Note: TradeDecision has no FAILED status in the current "
                "schema, so stuck RISK_APPROVED rows are the closest real proxy for "
                "repeated execution failure.",
                evidence={
                    "stuck_count": count,
                    "stuck_over_critical_threshold": crit_count,
                    "warn_threshold_minutes": _STUCK_RISK_APPROVED_WARN_MINUTES,
                    "crit_threshold_minutes": _STUCK_RISK_APPROVED_CRIT_MINUTES,
                },
                recommended_action=(
                    "Check Execution Engine logs for repeated 'Execution engine error' "
                    "entries on these decision_ids (missing price data, DB error, etc.)."
                ),
            )
        ]

    # ── 8. RISK_GATE_STUCK (proxy: stuck PENDING actionable decisions) ──────

    async def _check_risk_gate_stuck(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        warn_cutoff = now - timedelta(minutes=_RISK_GATE_STUCK_WARN_MINUTES)
        result = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.status == "PENDING",
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.decided_at < warn_cutoff,
            )
        )
        count = int(result.scalar_one() or 0)
        if count == 0:
            return []

        crit_cutoff = now - timedelta(minutes=_RISK_GATE_STUCK_CRIT_MINUTES)
        crit_result = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.status == "PENDING",
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.decided_at < crit_cutoff,
            )
        )
        crit_count = int(crit_result.scalar_one() or 0)
        severity = "CRITICAL" if crit_count > 0 else "WARNING"

        return [
            _alert(
                code="RISK_GATE_STUCK",
                severity=severity,
                message=f"{count} actionable decision(s) (OPEN_LONG_YES/NO) have been "
                f"PENDING for more than {_RISK_GATE_STUCK_WARN_MINUTES:.0f} minutes "
                "without a Risk Engine verdict. Note: there is no 'risk_gated' field "
                "in the current schema, so stuck PENDING rows are the closest real "
                "proxy.",
                evidence={
                    "stuck_count": count,
                    "stuck_over_critical_threshold": crit_count,
                    "warn_threshold_minutes": _RISK_GATE_STUCK_WARN_MINUTES,
                    "crit_threshold_minutes": _RISK_GATE_STUCK_CRIT_MINUTES,
                },
                recommended_action=(
                    "Check the Risk Engine heartbeat/logs; the Risk Engine loop may "
                    "be stalled or erroring before it can update these rows."
                ),
            )
        ]

    # ── 9. DUPLICATE_EXECUTION ───────────────────────────────────────────────
    #
    # Phase 12L: multiple OPEN positions per condition_id is VALID (multi-entry
    # / scale-in).  This check is now scoped to true execution replay: the same
    # order_id producing more than one position row, which indicates the
    # Execution Engine processed a fill event twice and is an integrity error
    # regardless of the multi-entry policy.

    async def _check_duplicate_execution(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        """
        Fire when any order_id has produced more than one position row.

        Multiple OPEN positions for the same condition_id are intentional
        (LOT 1 / LOT 2 / LOT 3 scale-in).  A real integrity violation is
        when the Execution Engine replays the same order fill and inserts a
        second position for the same order_id.
        """
        from app.models.order import Order  # local import avoids circular dep

        result = await session.execute(
            select(Position.order_id, func.count().label("cnt"))
            .where(Position.status == "OPEN", Position.order_id.isnot(None))
            .group_by(Position.order_id)
            .having(func.count() > 1)
        )
        rows = result.all()
        if not rows:
            return []
        return [
            _alert(
                code="DUPLICATE_EXECUTION",
                severity="CRITICAL",
                message=(
                    f"{len(rows)} order_id(s) have produced more than one OPEN "
                    "position — the Execution Engine appears to have replayed a "
                    "fill event."
                ),
                evidence={
                    "count": len(rows),
                    "examples": [
                        {"order_id": r.order_id, "open_count": r.cnt}
                        for r in rows[:10]
                    ],
                },
                recommended_action=(
                    "Inspect execution_engine.py idempotency guard; each order_id "
                    "must produce exactly one position.  Check for duplicate "
                    "fill-event delivery from the order gateway."
                ),
            )
        ]

    # ── 10. PORTFOLIO_EXPOSURE_HIGH ──────────────────────────────────────────

    async def _check_portfolio_exposure_high(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        result = await session.execute(
            select(
                func.coalesce(func.sum(Position.quantity * Position.entry_price), 0.0)
            ).where(Position.status == "OPEN")
        )
        exposure = float(result.scalar_one() or 0.0)
        cap = settings.PORTFOLIO_MAX_EXPOSURE_USDC
        if cap <= 0:
            return []
        ratio = exposure / cap

        if ratio >= 1.0:
            severity = "CRITICAL"
        elif ratio >= 0.8:
            severity = "WARNING"
        else:
            return []

        return [
            _alert(
                code="PORTFOLIO_EXPOSURE_HIGH",
                severity=severity,
                message=f"Open exposure ${exposure:.2f} is {ratio * 100:.0f}% of the "
                f"configured ${cap:.2f} PORTFOLIO_MAX_EXPOSURE_USDC cap.",
                evidence={
                    "open_exposure_usdc": round(exposure, 2),
                    "cap_usdc": cap,
                    "ratio": round(ratio, 3),
                },
                recommended_action=(
                    "No action required if the Risk Engine's MAX_EXPOSURE rule is "
                    "the reason new entries are being blocked; this alert is "
                    "informational unless ratio >= 1.0, which should be impossible "
                    "under an intact risk gate and warrants investigation."
                ),
            )
        ]

    # ── 11. PAPER_PNL_ANOMALY ────────────────────────────────────────────────

    async def _check_paper_pnl_anomaly(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        # Closed positions must always have a realized_pnl computed.
        null_result = await session.execute(
            select(func.count(Position.id)).where(
                Position.status == "CLOSED", Position.realized_pnl.is_(None)
            )
        )
        null_count = int(null_result.scalar_one() or 0)

        # A binary-market token pays out between 0 and 1, so |realized_pnl|
        # can never legitimately exceed quantity * 1.0 (plus zero fees in
        # paper mode). A larger magnitude is impossible and indicates a bug.
        impossible_result = await session.execute(
            select(Position.id, Position.quantity, Position.realized_pnl).where(
                Position.status == "CLOSED",
                Position.realized_pnl.is_not(None),
                func.abs(Position.realized_pnl) > Position.quantity,
            )
        )
        impossible_rows = impossible_result.all()

        if null_count == 0 and not impossible_rows:
            return []

        evidence: dict[str, Any] = {
            "null_realized_pnl_count": null_count,
            "impossible_magnitude_count": len(impossible_rows),
        }
        if impossible_rows:
            evidence["examples"] = [
                {"position_id": r.id, "quantity": r.quantity, "realized_pnl": r.realized_pnl}
                for r in impossible_rows[:10]
            ]

        return [
            _alert(
                code="PAPER_PNL_ANOMALY",
                severity="CRITICAL",
                message=f"{null_count} CLOSED position(s) missing realized_pnl and "
                f"{len(impossible_rows)} with a realized_pnl magnitude exceeding "
                "the maximum possible binary-market payoff.",
                evidence=evidence,
                recommended_action=(
                    "Investigate ExecutionEngine.close position path and "
                    "PositionService.close_position() for these position_ids; "
                    "do not trust downstream analytics until resolved."
                ),
            )
        ]

    # ── 12. FORCED_EXIT_PENDING ──────────────────────────────────────────────

    async def _check_forced_exit_pending(
        self, session: AsyncSession, now: datetime
    ) -> list[dict]:
        warn_cutoff = now - timedelta(minutes=_FORCED_EXIT_WARN_MINUTES)

        result = await session.execute(
            select(Position.id, Position.condition_id, Position.asset, Position.timeframe, MarketUniverse.end_time)
            .join(MarketUniverse, MarketUniverse.condition_id == Position.condition_id)
            .where(Position.status == "OPEN", MarketUniverse.end_time < warn_cutoff)
        )
        expired_open = result.all()
        if not expired_open:
            return []

        position_ids = [r.id for r in expired_open]
        close_result = await session.execute(
            select(TradeDecision.target_position_id).where(
                TradeDecision.decision == "CLOSE_POSITION",
                TradeDecision.target_position_id.in_(position_ids),
            )
        )
        already_targeted = {row[0] for row in close_result.all()}

        pending = [r for r in expired_open if r.id not in already_targeted]
        if not pending:
            return []

        crit_cutoff = now - timedelta(minutes=_FORCED_EXIT_CRIT_MINUTES)
        critical_pending = [r for r in pending if r.end_time < crit_cutoff]
        severity = "CRITICAL" if critical_pending else "WARNING"

        return [
            _alert(
                code="FORCED_EXIT_PENDING",
                severity=severity,
                message=f"{len(pending)} expired OPEN position(s) have no "
                "CLOSE_POSITION decision at all, more than "
                f"{_FORCED_EXIT_WARN_MINUTES:.0f} minutes past expiry.",
                evidence={
                    "count": len(pending),
                    "critical_count": len(critical_pending),
                    "examples": [
                        {
                            "position_id": r.id,
                            "condition_id": r.condition_id[:16],
                            "asset": r.asset,
                            "timeframe": r.timeframe,
                            "end_time": r.end_time.isoformat(),
                        }
                        for r in pending[:10]
                    ],
                },
                recommended_action=(
                    "Check Exit Engine EXPIRY_EXIT trigger and heartbeat; a healthy "
                    "system should generate a CLOSE_POSITION decision within "
                    "EXIT_FORCE_EXPIRY_MINUTES of expiry."
                ),
            )
        ]
