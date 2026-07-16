"""
EngineScorecardService tests — Phase 5.

Uses in-memory SQLite.  Tests cover empty state, each engine dimension,
composite scoring, and grade derivation.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models
from app.core.database import Base
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.models.signal import Signal
from app.models.trade_decision import TradeDecision
from app.services.engine_scorecard_service import EngineScorecardService, _grade, _safe_pct

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
def service() -> EngineScorecardService:
    return EngineScorecardService()


def _now():
    return datetime.now(timezone.utc)


def _signal(condition_id: str, asset: str = "BTC", tf: str = "5m") -> Signal:
    return Signal(
        condition_id=condition_id,
        asset=asset,
        timeframe=tf,
        signal_type="MID_MOVE",
        severity="MEDIUM",
        yes_mid_before=0.50,
        yes_mid_after=0.51,
        yes_mid_delta=0.01,
        detected_at=_now(),
    )


def _opportunity(condition_id: str, score: float = 50.0) -> Opportunity:
    return Opportunity(
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        opportunity_score=score,
        direction="BUY_YES",
        yes_mid=0.51,
        yes_bid=0.50,
        yes_ask=0.52,
        evaluated_at=_now(),
    )


def _decision(
    condition_id: str,
    decision: str = "OPEN_LONG_YES",
    status: str = "EXECUTED",
    score: float = 55.0,
) -> TradeDecision:
    return TradeDecision(
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        decision=decision,
        status=status,
        opportunity_score=score,
        direction="BUY_YES",
    )


def _closed_pos(order_id: int, pnl: float = 0.10) -> Position:
    return Position(
        order_id=order_id,
        condition_id=f"cond_{order_id}",
        asset="BTC",
        timeframe="5m",
        side="LONG_YES",
        quantity=10.0,
        entry_price=0.50,
        status="CLOSED",
        realized_pnl=pnl,
        opened_at=_now(),
        closed_at=_now(),
    )


# ── helpers ────────────────────────────────────────────────────────────────────

def test_grade_boundaries():
    assert _grade(80.0) == "A"
    assert _grade(60.0) == "B"
    assert _grade(40.0) == "C"
    assert _grade(20.0) == "D"
    assert _grade(0.0) == "F"

def test_safe_pct_zero_denominator():
    assert _safe_pct(5, 0) == 0.0

def test_safe_pct_normal():
    assert abs(_safe_pct(1, 2) - 50.0) < 0.01

def test_safe_pct_full():
    assert abs(_safe_pct(3, 3) - 100.0) < 0.01


# ── empty state ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_empty_db_returns_zero_scores(
    service: EngineScorecardService, db_session: AsyncSession
):
    scorecard = await service.compute_scorecard(db_session)
    assert scorecard["signal_accuracy"]["score"] == 0.0
    assert scorecard["opportunity_accuracy"]["score"] == 0.0
    assert scorecard["strategy_execution_rate"]["score"] == 0.0
    assert scorecard["execution_win_rate"]["score"] == 0.0
    # risk_effectiveness is 50.0 when no blocked trades (neutral)
    assert scorecard["risk_effectiveness"]["score"] == 50.0


@pytest.mark.anyio
async def test_empty_db_composite_and_grade_present(
    service: EngineScorecardService, db_session: AsyncSession
):
    scorecard = await service.compute_scorecard(db_session)
    assert "composite_score" in scorecard
    assert "composite_grade" in scorecard
    assert 0.0 <= scorecard["composite_score"] <= 100.0
    assert scorecard["composite_grade"] in ("A", "B", "C", "D", "F")


# ── signal_accuracy ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_signal_accuracy_100_percent(
    service: EngineScorecardService, db_session: AsyncSession
):
    """One signal condition + one executed OPEN_LONG for same condition → 100%."""
    db_session.add(_signal("c1"))
    db_session.add(_decision("c1", decision="OPEN_LONG_YES", status="EXECUTED"))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert abs(sc["signal_accuracy"]["score"] - 100.0) < 0.1


@pytest.mark.anyio
async def test_signal_accuracy_zero_when_no_executions(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add(_signal("c1"))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert sc["signal_accuracy"]["score"] == 0.0


# ── opportunity_accuracy ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_opportunity_accuracy_zero_when_no_high_score_opps(
    service: EngineScorecardService, db_session: AsyncSession
):
    """No high-score opportunities → denominator=0 → score=0."""
    db_session.add(_opportunity("c1", score=20.0))  # below threshold
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert sc["opportunity_accuracy"]["score"] == 0.0


@pytest.mark.anyio
async def test_opportunity_accuracy_with_high_score_and_execution(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add(_opportunity("c1", score=60.0))
    db_session.add(_decision("c1", decision="OPEN_LONG_YES", status="EXECUTED"))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert sc["opportunity_accuracy"]["score"] > 0.0


# ── strategy_execution_rate ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_strategy_execution_rate_100(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add(_decision("c1", status="EXECUTED"))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert abs(sc["strategy_execution_rate"]["score"] - 100.0) < 0.1


@pytest.mark.anyio
async def test_strategy_execution_rate_50(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add_all([
        _decision("c1", status="EXECUTED"),
        _decision("c2", status="BLOCKED"),
    ])
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert abs(sc["strategy_execution_rate"]["score"] - 50.0) < 0.1


@pytest.mark.anyio
async def test_strategy_execution_rate_zero_when_no_decisions(
    service: EngineScorecardService, db_session: AsyncSession
):
    sc = await service.compute_scorecard(db_session)
    assert sc["strategy_execution_rate"]["score"] == 0.0


# ── execution_win_rate ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_execution_win_rate_100(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add(_closed_pos(1, pnl=0.10))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert abs(sc["execution_win_rate"]["score"] - 100.0) < 0.1


@pytest.mark.anyio
async def test_execution_win_rate_50(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add_all([
        _closed_pos(1, pnl=0.10),
        _closed_pos(2, pnl=-0.05),
    ])
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert abs(sc["execution_win_rate"]["score"] - 50.0) < 0.1


@pytest.mark.anyio
async def test_execution_win_rate_zero_when_all_losses(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add(_closed_pos(1, pnl=-0.10))
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert sc["execution_win_rate"]["score"] == 0.0


# ── risk_effectiveness ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_risk_effectiveness_neutral_when_no_blocks(
    service: EngineScorecardService, db_session: AsyncSession
):
    """No blocked trades → risk_score = 50 (neutral)."""
    sc = await service.compute_scorecard(db_session)
    assert sc["risk_effectiveness"]["score"] == 50.0


@pytest.mark.anyio
async def test_risk_effectiveness_non_zero_with_blocks(
    service: EngineScorecardService, db_session: AsyncSession
):
    db_session.add_all([
        _decision("c1", status="BLOCKED"),
        _decision("c2", status="EXECUTED"),
    ])
    await db_session.commit()

    sc = await service.compute_scorecard(db_session)
    assert sc["risk_effectiveness"]["score"] > 0.0


# ── composite and grade ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_composite_grade_matches_score(
    service: EngineScorecardService, db_session: AsyncSession
):
    sc = await service.compute_scorecard(db_session)
    composite = sc["composite_score"]
    assert sc["composite_grade"] == _grade(composite)


@pytest.mark.anyio
async def test_scorecard_all_fields_present(
    service: EngineScorecardService, db_session: AsyncSession
):
    sc = await service.compute_scorecard(db_session)
    required = {
        "signal_accuracy",
        "opportunity_accuracy",
        "strategy_execution_rate",
        "execution_win_rate",
        "risk_effectiveness",
        "composite_score",
        "composite_grade",
    }
    assert required.issubset(sc.keys())

    # Each engine entry has score, label, numerator, denominator
    for key in required - {"composite_score", "composite_grade"}:
        entry = sc[key]
        assert "score" in entry
        assert "label" in entry
        assert "numerator" in entry
        assert "denominator" in entry
