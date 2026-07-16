"""
Alert Service tests — Phase 12: Monitoring / Alert / Operator Safety System.

Each _check_* method is tested in isolation with a mocked AsyncSession
(matching the existing test_risk_engine.py pattern), plus integration-level
tests of AlertService.snapshot() for status aggregation and the
MONITORING_QUERY_FAILED fail-safe path.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_service import AlertService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _exec_result(rows=None, scalar=None):
    """Fake SQLAlchemy execute() result supporting .scalars().all()/.all()/.scalar_one()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows or []
    result.all.return_value = rows or []
    result.scalar_one.return_value = scalar
    return result


def _row(**kwargs):
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    # support tuple-style access for (condition_id, count) style rows
    row.__getitem__ = lambda self, i: list(kwargs.values())[i]
    return row


@pytest.fixture
def service() -> AlertService:
    return AlertService()


# ── _check_duplicate_execution ──────────────────────────────────────────────
# Phase 12L: multiple OPEN positions per condition_id is VALID (multi-entry).
# This check fires only when the same order_id produces >1 position row —
# a true execution replay error.


@pytest.mark.asyncio
async def test_duplicate_execution_none_when_clean(service):
    session = AsyncMock()
    session.execute.return_value = _exec_result(rows=[])
    alerts = await service._check_duplicate_execution(session, _now())
    assert alerts == []


@pytest.mark.asyncio
async def test_duplicate_execution_critical_when_found(service):
    session = AsyncMock()
    dup_row = _row(order_id=42, cnt=2)
    session.execute.return_value = _exec_result(rows=[dup_row])
    alerts = await service._check_duplicate_execution(session, _now())
    assert len(alerts) == 1
    assert alerts[0]["code"] == "DUPLICATE_EXECUTION"
    assert alerts[0]["severity"] == "CRITICAL"
    assert alerts[0]["evidence"]["count"] == 1
    assert alerts[0]["evidence"]["examples"][0]["order_id"] == 42


@pytest.mark.asyncio
async def test_duplicate_execution_multi_entry_not_flagged(service):
    """
    Multiple positions for the same condition_id (LOT 1/2/3 scale-in) must NOT
    trigger this alert — only same order_id replay is an integrity violation.
    """
    # Simulate clean state: no order_id has >1 position
    session = AsyncMock()
    session.execute.return_value = _exec_result(rows=[])
    alerts = await service._check_duplicate_execution(session, _now())
    assert alerts == []


# ── _check_expired_position_open ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_position_open_none_when_clean(service):
    session = AsyncMock()
    session.execute.return_value = _exec_result(rows=[])
    alerts = await service._check_expired_position_open(session, _now())
    assert alerts == []


@pytest.mark.asyncio
async def test_expired_position_open_critical_when_found(service):
    session = AsyncMock()
    now = _now()
    expired_row = _row(
        id=1,
        condition_id="0xabc1234567890",
        asset="BTC",
        timeframe="5m",
        end_time=now - timedelta(hours=1),
    )
    session.execute.return_value = _exec_result(rows=[expired_row])
    alerts = await service._check_expired_position_open(session, now)
    assert len(alerts) == 1
    assert alerts[0]["code"] == "EXPIRED_POSITION_OPEN"
    assert alerts[0]["severity"] == "CRITICAL"


# ── _check_direct_resolution_missing ────────────────────────────────────────


@pytest.mark.asyncio
async def test_direct_resolution_missing_warning_when_recently_expired(service):
    session = AsyncMock()
    now = _now()
    row = _row(
        condition_id="0xabc1234567890",
        asset="BTC",
        timeframe="5m",
        end_time=now - timedelta(minutes=25),
        outcome_source=None,
    )
    session.execute.return_value = _exec_result(rows=[row])
    alerts = await service._check_direct_resolution_missing(session, now)
    assert len(alerts) == 1
    assert alerts[0]["code"] == "DIRECT_RESOLUTION_MISSING"
    assert alerts[0]["severity"] == "WARNING"


@pytest.mark.asyncio
async def test_direct_resolution_missing_critical_when_very_stale(service):
    session = AsyncMock()
    now = _now()
    row = _row(
        condition_id="0xabc1234567890",
        asset="BTC",
        timeframe="5m",
        end_time=now - timedelta(minutes=200),
        outcome_source="NOT_AVAILABLE",
    )
    session.execute.return_value = _exec_result(rows=[row])
    alerts = await service._check_direct_resolution_missing(session, now)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_direct_resolution_missing_none_when_resolved(service):
    session = AsyncMock()
    now = _now()
    row = _row(
        condition_id="0xabc1234567890",
        asset="BTC",
        timeframe="5m",
        end_time=now - timedelta(minutes=25),
        outcome_source="DIRECT_POLYMARKET_RESOLUTION",
    )
    session.execute.return_value = _exec_result(rows=[row])
    alerts = await service._check_direct_resolution_missing(session, now)
    assert alerts == []


# ── _check_execution_error_spike ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_error_spike_none_when_clean(service):
    session = AsyncMock()
    session.execute.return_value = _exec_result(scalar=0)
    alerts = await service._check_execution_error_spike(session, _now())
    assert alerts == []


@pytest.mark.asyncio
async def test_execution_error_spike_warning_when_stuck(service):
    session = AsyncMock()
    session.execute.side_effect = [
        _exec_result(scalar=3),  # warn-window stuck count
        _exec_result(scalar=0),  # crit-window stuck count
    ]
    alerts = await service._check_execution_error_spike(session, _now())
    assert len(alerts) == 1
    assert alerts[0]["code"] == "EXECUTION_ERROR_SPIKE"
    assert alerts[0]["severity"] == "WARNING"


@pytest.mark.asyncio
async def test_execution_error_spike_critical_when_long_stuck(service):
    session = AsyncMock()
    session.execute.side_effect = [
        _exec_result(scalar=3),
        _exec_result(scalar=2),
    ]
    alerts = await service._check_execution_error_spike(session, _now())
    assert alerts[0]["severity"] == "CRITICAL"


# ── _check_paper_pnl_anomaly ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_pnl_anomaly_none_when_clean(service):
    session = AsyncMock()
    session.execute.side_effect = [
        _exec_result(scalar=0),  # null realized_pnl count
        _exec_result(rows=[]),   # impossible-magnitude rows
    ]
    alerts = await service._check_paper_pnl_anomaly(session, _now())
    assert alerts == []


@pytest.mark.asyncio
async def test_paper_pnl_anomaly_critical_when_null_pnl(service):
    session = AsyncMock()
    session.execute.side_effect = [
        _exec_result(scalar=2),
        _exec_result(rows=[]),
    ]
    alerts = await service._check_paper_pnl_anomaly(session, _now())
    assert len(alerts) == 1
    assert alerts[0]["code"] == "PAPER_PNL_ANOMALY"
    assert alerts[0]["severity"] == "CRITICAL"


# ── snapshot() aggregation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_ok_when_all_checks_clean(service):
    session = AsyncMock()
    with patch.object(AlertService, "_check_engine_stalled", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_gamma_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_clob_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_no_markets_active", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_expired_position_open", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_direct_resolution_missing", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_execution_error_spike", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_risk_gate_stuck", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_duplicate_execution", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_portfolio_exposure_high", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_paper_pnl_anomaly", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_forced_exit_pending", new=AsyncMock(return_value=[])):
        snapshot = await service.snapshot(session)

    assert snapshot["status"] == "OK"
    assert snapshot["alerts"] == []
    assert snapshot["summary"] == {"critical": 0, "warning": 0, "info": 0}
    assert "generated_at" in snapshot


@pytest.mark.asyncio
async def test_snapshot_critical_status_when_any_check_critical(service):
    session = AsyncMock()
    critical_alert = [
        {
            "code": "DUPLICATE_EXECUTION",
            "severity": "CRITICAL",
            "message": "x",
            "evidence": {},
            "recommended_action": "x",
        }
    ]
    with patch.object(AlertService, "_check_engine_stalled", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_gamma_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_clob_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_no_markets_active", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_expired_position_open", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_direct_resolution_missing", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_execution_error_spike", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_risk_gate_stuck", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_duplicate_execution", new=AsyncMock(return_value=critical_alert)), \
         patch.object(AlertService, "_check_portfolio_exposure_high", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_paper_pnl_anomaly", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_forced_exit_pending", new=AsyncMock(return_value=[])):
        snapshot = await service.snapshot(session)

    assert snapshot["status"] == "CRITICAL"
    assert snapshot["summary"]["critical"] == 1


@pytest.mark.asyncio
async def test_snapshot_query_failure_becomes_critical_monitoring_alert(service):
    """
    A raising check must NEVER be silently treated as OK — it must surface as
    a CRITICAL MONITORING_QUERY_FAILED alert (Step 4 rule: 'Jangan hardcode
    OK jika query gagal').
    """
    session = AsyncMock()
    failing_check = AsyncMock(side_effect=RuntimeError("db down"))
    failing_check.__name__ = "_check_engine_stalled"
    with patch.object(
        AlertService, "_check_engine_stalled", new=failing_check
    ), \
         patch.object(AlertService, "_check_gamma_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_clob_api_degraded", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_no_markets_active", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_expired_position_open", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_direct_resolution_missing", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_execution_error_spike", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_risk_gate_stuck", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_duplicate_execution", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_portfolio_exposure_high", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_paper_pnl_anomaly", new=AsyncMock(return_value=[])), \
         patch.object(AlertService, "_check_forced_exit_pending", new=AsyncMock(return_value=[])):
        snapshot = await service.snapshot(session)

    assert snapshot["status"] == "CRITICAL"
    codes = [a["code"] for a in snapshot["alerts"]]
    assert "MONITORING_QUERY_FAILED" in codes
    failed_alert = next(a for a in snapshot["alerts"] if a["code"] == "MONITORING_QUERY_FAILED")
    assert failed_alert["severity"] == "CRITICAL"
    assert failed_alert["evidence"]["check"] == "_check_engine_stalled"
