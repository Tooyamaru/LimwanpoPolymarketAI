"""
Performance Analytics Service tests — Layers 15 & Phase 4 Part C.

Uses in-memory SQLite (aiosqlite) for full isolation.
Covers both the existing metrics and Phase 4 additions:
  avg_hold_time_minutes, longest_hold_time_minutes, shortest_hold_time_minutes,
  mae_usdc, mfe_usdc, opportunity_conversion_rate,
  signal_precision, avg_winner_duration_minutes, avg_loser_duration_minutes,
  avg_fee_usdc, avg_slippage_usdc,
  avg_time_to_stop_minutes, avg_time_to_profit_minutes.
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models  # registers all ORM models
from app.core.database import Base
from app.services.performance_analytics_service import PerformanceAnalyticsService
from app.models.position import Position
from app.models.trade_decision import TradeDecision

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def service() -> PerformanceAnalyticsService:
    return PerformanceAnalyticsService()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _closed_position(
    order_id: int,
    condition_id: str,
    pnl: float,
    hold_minutes: float,
    close_reason: str | None = None,
    total_fee_usdc: float = 0.0,
) -> Position:
    now = _now()
    return Position(
        order_id=order_id,
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        side="LONG_NO",
        quantity=50.0,
        entry_price=0.50,
        status="CLOSED",
        realized_pnl=pnl,
        opened_at=now - timedelta(minutes=hold_minutes),
        closed_at=now,
        close_reason=close_reason,
        total_fee_usdc=total_fee_usdc,
    )


# ── empty-state defaults ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_empty_state_all_new_fields_zero(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    result = await service.get_performance_analytics(db_session)
    assert result["avg_hold_time_minutes"] == 0.0
    assert result["longest_hold_time_minutes"] == 0.0
    assert result["shortest_hold_time_minutes"] == 0.0
    assert result["mae_usdc"] == 0.0
    assert result["mfe_usdc"] == 0.0
    assert result["opportunity_conversion_rate"] == 0.0
    assert result["signal_precision"] == 0.0
    assert result["avg_winner_duration_minutes"] == 0.0
    assert result["avg_loser_duration_minutes"] == 0.0
    assert result["avg_fee_usdc"] == 0.0
    assert result["avg_slippage_usdc"] == 0.0
    assert result["avg_time_to_stop_minutes"] == 0.0
    assert result["avg_time_to_profit_minutes"] == 0.0


@pytest.mark.anyio
async def test_empty_state_existing_fields_intact(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    result = await service.get_performance_analytics(db_session)
    assert result["total_trades"] == 0
    assert result["win_rate"] == 0.0
    assert result["net_profit"] == 0.0
    assert result["profit_factor"] is None


# ── holding time metrics ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_avg_hold_time_single_trade(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add(_closed_position(1, "c1", -0.50, hold_minutes=30.0))
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert abs(result["avg_hold_time_minutes"] - 30.0) < 0.1
    assert abs(result["longest_hold_time_minutes"] - 30.0) < 0.1
    assert abs(result["shortest_hold_time_minutes"] - 30.0) < 0.1


@pytest.mark.anyio
async def test_avg_hold_time_multiple_trades(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        _closed_position(1, "c1", -0.50, hold_minutes=10.0),
        _closed_position(2, "c2", -0.50, hold_minutes=30.0),
        _closed_position(3, "c3", -0.50, hold_minutes=50.0),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # avg = (10 + 30 + 50) / 3 = 30 min
    assert abs(result["avg_hold_time_minutes"] - 30.0) < 0.1
    assert abs(result["longest_hold_time_minutes"] - 50.0) < 0.1
    assert abs(result["shortest_hold_time_minutes"] - 10.0) < 0.1


# ── MAE / MFE metrics ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mae_mfe_all_losses(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        _closed_position(1, "c1", -0.50, 5.0),
        _closed_position(2, "c2", -1.00, 5.0),
        _closed_position(3, "c3", -0.25, 5.0),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # MAE = worst (most negative) = -1.00
    assert abs(result["mae_usdc"] - (-1.00)) < 1e-6
    # MFE = best (least negative in all-loss case) = -0.25
    assert abs(result["mfe_usdc"] - (-0.25)) < 1e-6


@pytest.mark.anyio
async def test_mae_mfe_mixed_results(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        _closed_position(1, "c1", -0.50, 5.0),  # loss
        _closed_position(2, "c2",  0.10, 5.0),  # win
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert abs(result["mae_usdc"] - (-0.50)) < 1e-6
    assert abs(result["mfe_usdc"] - 0.10) < 1e-6


# ── opportunity conversion rate ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_conversion_rate_zero_when_no_decisions(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    result = await service.get_performance_analytics(db_session)
    assert result["opportunity_conversion_rate"] == 0.0


@pytest.mark.anyio
async def test_conversion_rate_100_when_all_executed(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        TradeDecision(
            condition_id="c1", asset="BTC", timeframe="5m",
            decision="OPEN_LONG_NO", status="EXECUTED", opportunity_score=34.0,
            direction="BUY_NO",
        ),
        TradeDecision(
            condition_id="c2", asset="ETH", timeframe="5m",
            decision="OPEN_LONG_YES", status="EXECUTED", opportunity_score=34.0,
            direction="BUY_YES",
        ),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert abs(result["opportunity_conversion_rate"] - 100.0) < 1e-4


@pytest.mark.anyio
async def test_conversion_rate_50_percent(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        TradeDecision(
            condition_id="c1", asset="BTC", timeframe="5m",
            decision="OPEN_LONG_NO", status="EXECUTED", opportunity_score=34.0,
            direction="BUY_NO",
        ),
        TradeDecision(
            condition_id="c2", asset="ETH", timeframe="5m",
            decision="OPEN_LONG_NO", status="BLOCKED", opportunity_score=34.0,
            direction="BUY_NO",
        ),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert abs(result["opportunity_conversion_rate"] - 50.0) < 1e-4


@pytest.mark.anyio
async def test_conversion_rate_excludes_watch_and_close_decisions(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    """WATCH and CLOSE_POSITION decisions must not appear in the denominator."""
    db_session.add_all([
        TradeDecision(
            condition_id="c1", asset="BTC", timeframe="5m",
            decision="OPEN_LONG_NO", status="EXECUTED", opportunity_score=34.0,
            direction="BUY_NO",
        ),
        TradeDecision(
            condition_id="c2", asset="BTC", timeframe="5m",
            decision="WATCH", status="PENDING", opportunity_score=25.0,
            direction="BUY_NO",
        ),
        TradeDecision(
            condition_id="c3", asset="BTC", timeframe="5m",
            decision="CLOSE_POSITION", status="EXECUTED", opportunity_score=34.0,
            direction="BUY_NO",
        ),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # Only 1 OPEN_LONG decision and it was EXECUTED → 100%
    assert abs(result["opportunity_conversion_rate"] - 100.0) < 1e-4


# ── Phase 4 Part C: signal_precision ─────────────────────────────────────────

@pytest.mark.anyio
async def test_signal_precision_equals_win_rate(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    """signal_precision is defined as win_rate in this system."""
    db_session.add_all([
        _closed_position(1, "c1", 0.20, 5.0),   # win
        _closed_position(2, "c2", -0.10, 5.0),  # loss
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["signal_precision"] == result["win_rate"]
    assert abs(result["signal_precision"] - 50.0) < 1e-4


# ── Phase 4 Part C: winner / loser durations ──────────────────────────────────

@pytest.mark.anyio
async def test_avg_winner_loser_duration(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        _closed_position(1, "c1", 0.20, hold_minutes=10.0),   # winner → 10 min
        _closed_position(2, "c2", 0.10, hold_minutes=30.0),   # winner → 30 min
        _closed_position(3, "c3", -0.05, hold_minutes=50.0),  # loser  → 50 min
        _closed_position(4, "c4", -0.15, hold_minutes=20.0),  # loser  → 20 min
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # avg winner = (10 + 30) / 2 = 20 min
    assert abs(result["avg_winner_duration_minutes"] - 20.0) < 0.5
    # avg loser = (50 + 20) / 2 = 35 min
    assert abs(result["avg_loser_duration_minutes"] - 35.0) < 0.5


@pytest.mark.anyio
async def test_avg_winner_duration_zero_when_no_winners(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add(_closed_position(1, "c1", -0.10, hold_minutes=10.0))
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["avg_winner_duration_minutes"] == 0.0


@pytest.mark.anyio
async def test_avg_loser_duration_zero_when_no_losers(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add(_closed_position(1, "c1", 0.10, hold_minutes=10.0))
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["avg_loser_duration_minutes"] == 0.0


# ── Phase 4 Part D: avg_fee_usdc ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_avg_fee_zero_in_paper_mode(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    """Default paper mode has zero fees."""
    db_session.add_all([
        _closed_position(1, "c1", 0.10, 5.0, total_fee_usdc=0.0),
        _closed_position(2, "c2", 0.05, 5.0, total_fee_usdc=0.0),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["avg_fee_usdc"] == 0.0
    assert result["avg_slippage_usdc"] == 0.0


@pytest.mark.anyio
async def test_avg_fee_when_fees_present(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    """avg_fee_usdc averages total_fee_usdc across all closed positions."""
    db_session.add_all([
        _closed_position(1, "c1", 0.20, 5.0, total_fee_usdc=0.10),
        _closed_position(2, "c2", 0.10, 5.0, total_fee_usdc=0.20),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # avg = (0.10 + 0.20) / 2 = 0.15
    assert abs(result["avg_fee_usdc"] - 0.15) < 1e-6


# ── Phase 4 Part C: avg_time_to_stop / avg_time_to_profit ────────────────────

@pytest.mark.anyio
async def test_avg_time_to_stop_and_profit(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        _closed_position(1, "c1", -0.10, hold_minutes=15.0, close_reason="STOP_LOSS"),
        _closed_position(2, "c2", -0.20, hold_minutes=25.0, close_reason="STOP_LOSS"),
        _closed_position(3, "c3",  0.15, hold_minutes=10.0, close_reason="PROFIT_TARGET"),
        _closed_position(4, "c4",  0.20, hold_minutes=20.0, close_reason="PROFIT_TARGET"),
    ])
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    # avg stop = (15 + 25) / 2 = 20 min
    assert abs(result["avg_time_to_stop_minutes"] - 20.0) < 0.5
    # avg profit = (10 + 20) / 2 = 15 min
    assert abs(result["avg_time_to_profit_minutes"] - 15.0) < 0.5


@pytest.mark.anyio
async def test_avg_time_to_stop_zero_when_no_stops(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add(_closed_position(1, "c1", 0.10, hold_minutes=10.0, close_reason="PROFIT_TARGET"))
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["avg_time_to_stop_minutes"] == 0.0


@pytest.mark.anyio
async def test_avg_time_to_profit_zero_when_no_profit_targets(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    db_session.add(_closed_position(1, "c1", -0.10, hold_minutes=10.0, close_reason="STOP_LOSS"))
    await db_session.commit()
    result = await service.get_performance_analytics(db_session)
    assert result["avg_time_to_profit_minutes"] == 0.0


# ── all new fields present in response dict ───────────────────────────────────

@pytest.mark.anyio
async def test_all_new_fields_present_in_result(
    service: PerformanceAnalyticsService, db_session: AsyncSession
) -> None:
    result = await service.get_performance_analytics(db_session)
    required_fields = {
        "avg_hold_time_minutes",
        "longest_hold_time_minutes",
        "shortest_hold_time_minutes",
        "mae_usdc",
        "mfe_usdc",
        "opportunity_conversion_rate",
        "signal_precision",
        "avg_winner_duration_minutes",
        "avg_loser_duration_minutes",
        "avg_fee_usdc",
        "avg_slippage_usdc",
        "avg_time_to_stop_minutes",
        "avg_time_to_profit_minutes",
    }
    assert required_fields.issubset(set(result.keys())), (
        f"Missing fields: {required_fields - set(result.keys())}"
    )
