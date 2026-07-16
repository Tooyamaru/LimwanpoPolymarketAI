"""
TradeEvaluationService tests — Phase 5.

Uses in-memory SQLite for full isolation.
Covers scoring model, grade boundaries, summary aggregation,
upsert behaviour, and empty-state defaults.
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

import app.models  # registers all ORM models
from app.core.database import Base
from app.models.position import Position
from app.models.trade_evaluation import TradeEvaluation
from app.services.trade_evaluation_service import TradeEvaluationService, _grade, _clamp

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
def service() -> TradeEvaluationService:
    return TradeEvaluationService()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _closed_pos(
    order_id: int,
    *,
    pnl: float = 0.10,
    hold_minutes: float = 15.0,
    asset: str = "BTC",
    timeframe: str = "5m",
    entry_price: float = 0.50,
    quantity: float = 10.0,
    peak_pnl: float | None = None,
    close_reason: str | None = "PROFIT_TARGET",
    total_fee_usdc: float = 0.0,
) -> Position:
    now = _now()
    return Position(
        order_id=order_id,
        condition_id=f"cond_{order_id}",
        asset=asset,
        timeframe=timeframe,
        side="LONG_YES",
        quantity=quantity,
        entry_price=entry_price,
        status="CLOSED",
        realized_pnl=pnl,
        peak_pnl_usdc=peak_pnl,
        opened_at=now - timedelta(minutes=hold_minutes),
        closed_at=now,
        close_reason=close_reason,
        total_fee_usdc=total_fee_usdc,
    )


# ── helper: _grade ─────────────────────────────────────────────────────────────

def test_grade_A():
    assert _grade(80.0) == "A"
    assert _grade(100.0) == "A"

def test_grade_B():
    assert _grade(60.0) == "B"
    assert _grade(79.9) == "B"

def test_grade_C():
    assert _grade(40.0) == "C"
    assert _grade(59.9) == "C"

def test_grade_D():
    assert _grade(20.0) == "D"
    assert _grade(39.9) == "D"

def test_grade_F():
    assert _grade(0.0) == "F"
    assert _grade(19.9) == "F"


# ── helper: _clamp ─────────────────────────────────────────────────────────────

def test_clamp_within_range():
    assert _clamp(50.0) == 50.0

def test_clamp_below_zero():
    assert _clamp(-10.0) == 0.0

def test_clamp_above_hundred():
    assert _clamp(150.0) == 100.0


# ── empty state ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_evaluate_all_empty_db(
    service: TradeEvaluationService, db_session: AsyncSession
):
    result = await service.evaluate_all(db_session)
    assert result == []


@pytest.mark.anyio
async def test_get_evaluation_summary_empty(
    service: TradeEvaluationService, db_session: AsyncSession
):
    summary = await service.get_evaluation_summary(db_session)
    assert summary["total_evaluated"] == 0
    assert summary["avg_quality_score"] == 0.0
    assert summary["best_grade_asset"] is None
    assert summary["worst_grade_asset"] is None
    assert summary["grade_distribution"] == {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}


# ── basic evaluation ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_evaluate_single_position_returns_evaluation(
    service: TradeEvaluationService, db_session: AsyncSession
):
    pos = _closed_pos(1, pnl=0.50, hold_minutes=15.0, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.position_id == pos.id
    assert 0.0 <= ev.quality_score <= 100.0
    assert ev.grade in ("A", "B", "C", "D", "F")
    assert ev.realized_pnl == 0.50
    assert ev.asset == "BTC"
    assert ev.timeframe == "5m"


@pytest.mark.anyio
async def test_evaluate_all_creates_records(
    service: TradeEvaluationService, db_session: AsyncSession
):
    db_session.add_all([
        _closed_pos(1, pnl=0.10),
        _closed_pos(2, pnl=-0.05),
        _closed_pos(3, pnl=0.20),
    ])
    await db_session.commit()

    new_evals = await service.evaluate_all(db_session)
    assert len(new_evals) == 3

    # All persisted
    res = await db_session.execute(select(TradeEvaluation))
    all_evals = list(res.scalars().all())
    assert len(all_evals) == 3


@pytest.mark.anyio
async def test_evaluate_all_is_idempotent(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """Running evaluate_all twice must not create duplicates."""
    db_session.add(_closed_pos(1, pnl=0.10))
    await db_session.commit()

    first = await service.evaluate_all(db_session)
    second = await service.evaluate_all(db_session)

    assert len(first) == 1
    assert len(second) == 0  # already evaluated

    res = await db_session.execute(select(TradeEvaluation))
    assert len(list(res.scalars().all())) == 1


# ── scoring logic ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_entry_quality_at_mid_is_high(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """entry_price == 0.50 means perfect entry → entry_quality = 100."""
    pos = _closed_pos(1, entry_price=0.50, pnl=0.10)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.entry_quality == 100.0


@pytest.mark.anyio
async def test_entry_quality_far_from_mid_is_low(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """entry_price == 0.60 is 0.10 from mid → entry_quality = 0."""
    pos = _closed_pos(1, entry_price=0.60, pnl=0.10)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.entry_quality == 0.0


@pytest.mark.anyio
async def test_exit_quality_full_capture(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """realized == peak → exit_quality = 100."""
    pos = _closed_pos(1, pnl=1.00, peak_pnl=1.00, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.exit_quality == 100.0


@pytest.mark.anyio
async def test_exit_quality_partial_capture(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """realized = 0.5 * peak → exit_quality ≈ 50."""
    pos = _closed_pos(1, pnl=0.50, peak_pnl=1.00, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert abs(ev.exit_quality - 50.0) < 1.0


@pytest.mark.anyio
async def test_timing_score_perfect_hold(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """5m market typical hold = 15 min → hold_minutes=15 → timing_score=100."""
    pos = _closed_pos(1, timeframe="5m", hold_minutes=15.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.timing_score == 100.0


@pytest.mark.anyio
async def test_timing_score_too_short(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """Hold much shorter than typical → timing penalised."""
    pos = _closed_pos(1, timeframe="5m", hold_minutes=1.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.timing_score < 100.0


@pytest.mark.anyio
async def test_pnl_efficiency_full_capture(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """realized == peak → pnl_efficiency = 100."""
    pos = _closed_pos(1, pnl=1.00, peak_pnl=1.00, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.pnl_efficiency == 100.0


@pytest.mark.anyio
async def test_pnl_efficiency_partial_capture(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """realized = 0.5 * peak → pnl_efficiency = 50."""
    pos = _closed_pos(1, pnl=0.50, peak_pnl=1.00, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert abs(ev.pnl_efficiency - 50.0) < 0.1


@pytest.mark.anyio
async def test_pnl_efficiency_negative_trade_is_zero(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """Negative PnL → pnl_efficiency = 0."""
    pos = _closed_pos(1, pnl=-0.50, peak_pnl=0.20, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.pnl_efficiency == 0.0


@pytest.mark.anyio
async def test_pnl_efficiency_no_peak_but_profitable(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """No peak recorded but trade profitable → moderate 50."""
    pos = _closed_pos(1, pnl=0.50, peak_pnl=None, entry_price=0.50, quantity=10.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.pnl_efficiency == 50.0


# ── summary aggregation ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_summary_after_evaluations(
    service: TradeEvaluationService, db_session: AsyncSession
):
    db_session.add_all([
        _closed_pos(1, pnl=0.50, asset="BTC"),
        _closed_pos(2, pnl=-0.10, asset="ETH"),
        _closed_pos(3, pnl=0.30, asset="BTC"),
    ])
    await db_session.commit()
    await service.evaluate_all(db_session)

    summary = await service.get_evaluation_summary(db_session)
    assert summary["total_evaluated"] == 3
    assert 0.0 <= summary["avg_quality_score"] <= 100.0
    total_grades = sum(summary["grade_distribution"].values())
    assert total_grades == 3


@pytest.mark.anyio
async def test_summary_best_worst_asset(
    service: TradeEvaluationService, db_session: AsyncSession
):
    db_session.add_all([
        _closed_pos(1, pnl=1.00, asset="BTC", entry_price=0.50, quantity=20.0),
        _closed_pos(2, pnl=-1.00, asset="ETH", entry_price=0.50, quantity=20.0),
    ])
    await db_session.commit()
    await service.evaluate_all(db_session)

    summary = await service.get_evaluation_summary(db_session)
    assert summary["best_grade_asset"] is not None
    assert summary["worst_grade_asset"] is not None


# ── get_evaluation_for_position ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_evaluation_for_position_not_found(
    service: TradeEvaluationService, db_session: AsyncSession
):
    result = await service.get_evaluation_for_position(9999, db_session)
    assert result is None


@pytest.mark.anyio
async def test_get_evaluation_for_position_found(
    service: TradeEvaluationService, db_session: AsyncSession
):
    pos = _closed_pos(1, pnl=0.10)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    await service.evaluate_position(pos, db_session)
    found = await service.get_evaluation_for_position(pos.id, db_session)
    assert found is not None
    assert found.position_id == pos.id


# ── upsert (re-evaluate) ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_evaluate_position_upserts_existing(
    service: TradeEvaluationService, db_session: AsyncSession
):
    """evaluate_position must replace an existing evaluation, not create a duplicate."""
    pos = _closed_pos(1, pnl=0.10)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev1 = await service.evaluate_position(pos, db_session)
    ev2 = await service.evaluate_position(pos, db_session)

    res = await db_session.execute(
        select(TradeEvaluation).where(TradeEvaluation.position_id == pos.id)
    )
    rows = list(res.scalars().all())
    assert len(rows) == 1


# ── hold_minutes populated ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_hold_minutes_populated(
    service: TradeEvaluationService, db_session: AsyncSession
):
    pos = _closed_pos(1, hold_minutes=20.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.hold_minutes is not None
    assert abs(ev.hold_minutes - 20.0) < 0.5


# ── grade on evaluation record matches quality score ──────────────────────────

@pytest.mark.anyio
async def test_grade_consistent_with_quality_score(
    service: TradeEvaluationService, db_session: AsyncSession
):
    pos = _closed_pos(1)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    ev = await service.evaluate_position(pos, db_session)
    assert ev.grade == _grade(ev.quality_score)
