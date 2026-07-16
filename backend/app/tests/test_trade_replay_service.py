"""
TradeReplayService tests — Phase 5.

Uses in-memory SQLite.
Covers replay timeline construction, dataset export, and edge cases.
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models
from app.core.database import Base
from app.models.order import Order
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.models.trade_evaluation import TradeEvaluation
from app.services.trade_replay_service import TradeReplayService

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
def service() -> TradeReplayService:
    return TradeReplayService()


def _now():
    return datetime.now(timezone.utc)


def _make_order(decision_id: int = 1, condition_id: str = "c1") -> Order:
    return Order(
        decision_id=decision_id,
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        side="LONG_YES",
        quantity=10.0,
        requested_price=0.51,
        filled_price=0.51,
        status="FILLED",
        created_at=_now(),
        filled_at=_now(),
    )


def _make_decision(condition_id: str = "c1") -> TradeDecision:
    return TradeDecision(
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        decision="OPEN_LONG_YES",
        status="EXECUTED",
        opportunity_score=65.0,
        direction="BUY_YES",
        yes_mid=0.51,
    )


def _make_position(
    order_id: int,
    pnl: float = 0.20,
    hold_minutes: float = 15.0,
    condition_id: str = "c1",
) -> Position:
    now = _now()
    return Position(
        order_id=order_id,
        condition_id=condition_id,
        asset="BTC",
        timeframe="5m",
        side="LONG_YES",
        quantity=10.0,
        entry_price=0.50,
        exit_price=0.52,
        status="CLOSED",
        realized_pnl=pnl,
        peak_pnl_usdc=pnl * 1.2,
        opened_at=now - timedelta(minutes=hold_minutes),
        closed_at=now,
        close_reason="PROFIT_TARGET",
    )


# ── replay_position ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_replay_nonexistent_position_returns_none(
    service: TradeReplayService, db_session: AsyncSession
):
    result = await service.replay_position(9999, db_session)
    assert result is None


@pytest.mark.anyio
async def test_replay_open_position_returns_none(
    service: TradeReplayService, db_session: AsyncSession
):
    """Only CLOSED positions can be replayed."""
    pos = Position(
        order_id=1,
        condition_id="c1",
        asset="BTC",
        timeframe="5m",
        side="LONG_YES",
        quantity=10.0,
        entry_price=0.50,
        status="OPEN",  # not closed
        opened_at=_now(),
    )
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    assert result is None


@pytest.mark.anyio
async def test_replay_closed_position_returns_dict(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    assert result is not None
    assert result["position_id"] == pos.id
    assert result["asset"] == "BTC"
    assert result["timeframe"] == "5m"


@pytest.mark.anyio
async def test_replay_timeline_has_open_and_close_events(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    events = [e["event"] for e in result["timeline"]]
    assert "POSITION_OPENED" in events
    assert "POSITION_CLOSED" in events


@pytest.mark.anyio
async def test_replay_timeline_includes_entry_order(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    events = [e["event"] for e in result["timeline"]]
    assert "ENTRY_ORDER_FILLED" in events


@pytest.mark.anyio
async def test_replay_timeline_steps_are_sequential(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    steps = [e["step"] for e in result["timeline"]]
    assert steps == list(range(1, len(steps) + 1))


@pytest.mark.anyio
async def test_replay_hold_minutes_calculated(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id, hold_minutes=20.0)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    assert result["hold_minutes"] is not None
    assert abs(result["hold_minutes"] - 20.0) < 0.5


@pytest.mark.anyio
async def test_replay_evaluation_is_none_if_not_evaluated(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    assert result["evaluation"] is None


@pytest.mark.anyio
async def test_replay_evaluation_included_when_exists(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.flush()

    ev = TradeEvaluation(
        position_id=pos.id,
        asset="BTC",
        timeframe="5m",
        entry_quality=80.0,
        exit_quality=70.0,
        timing_score=100.0,
        pnl_efficiency=60.0,
        quality_score=77.5,
        grade="B",
        realized_pnl=0.20,
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    assert result["evaluation"] is not None
    assert result["evaluation"].grade == "B"


@pytest.mark.anyio
async def test_replay_with_peak_pnl_adds_peak_event(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id, pnl=0.20)
    pos.peak_pnl_usdc = 0.30  # peak above realized
    db_session.add(pos)
    await db_session.commit()
    await db_session.refresh(pos)

    result = await service.replay_position(pos.id, db_session)
    events = [e["event"] for e in result["timeline"]]
    assert "PEAK_PNL_REACHED" in events


# ── get_dataset ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_dataset_empty(
    service: TradeReplayService, db_session: AsyncSession
):
    data = await service.get_dataset(db_session)
    assert data["total_rows"] == 0
    assert data["rows"] == []


@pytest.mark.anyio
async def test_dataset_includes_closed_positions(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()

    data = await service.get_dataset(db_session)
    assert data["total_rows"] == 1
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["asset"] == "BTC"
    assert row["realized_pnl"] == pos.realized_pnl


@pytest.mark.anyio
async def test_dataset_open_positions_excluded(
    service: TradeReplayService, db_session: AsyncSession
):
    """Open positions must not appear in the dataset."""
    pos = Position(
        order_id=1,
        condition_id="c1",
        asset="BTC",
        timeframe="5m",
        side="LONG_YES",
        quantity=10.0,
        entry_price=0.50,
        status="OPEN",
        opened_at=_now(),
    )
    db_session.add(pos)
    await db_session.commit()

    data = await service.get_dataset(db_session)
    assert data["total_rows"] == 0


@pytest.mark.anyio
async def test_dataset_quality_score_null_without_evaluation(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()

    data = await service.get_dataset(db_session)
    assert data["rows"][0]["quality_score"] is None
    assert data["rows"][0]["grade"] is None


@pytest.mark.anyio
async def test_dataset_quality_score_populated_with_evaluation(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.flush()

    ev = TradeEvaluation(
        position_id=pos.id,
        asset="BTC",
        timeframe="5m",
        entry_quality=75.0,
        exit_quality=80.0,
        timing_score=90.0,
        pnl_efficiency=70.0,
        quality_score=78.75,
        grade="B",
        realized_pnl=0.20,
    )
    db_session.add(ev)
    await db_session.commit()

    data = await service.get_dataset(db_session)
    row = data["rows"][0]
    assert row["quality_score"] == 78.75
    assert row["grade"] == "B"


@pytest.mark.anyio
async def test_dataset_pagination(
    service: TradeReplayService, db_session: AsyncSession
):
    """limit/offset must paginate rows correctly."""
    orders = [_make_order(decision_id=i, condition_id=f"c{i}") for i in range(1, 6)]
    db_session.add_all(orders)
    await db_session.flush()

    positions = [
        _make_position(order_id=orders[i].id, condition_id=f"c{i+1}")
        for i in range(5)
    ]
    db_session.add_all(positions)
    await db_session.commit()

    data_all = await service.get_dataset(db_session, limit=1000, offset=0)
    assert data_all["total_rows"] == 5

    data_page = await service.get_dataset(db_session, limit=2, offset=0)
    assert len(data_page["rows"]) == 2

    data_offset = await service.get_dataset(db_session, limit=2, offset=4)
    assert len(data_offset["rows"]) == 1


@pytest.mark.anyio
async def test_dataset_row_has_required_fields(
    service: TradeReplayService, db_session: AsyncSession
):
    order = _make_order()
    db_session.add(order)
    await db_session.flush()

    pos = _make_position(order_id=order.id)
    db_session.add(pos)
    await db_session.commit()

    data = await service.get_dataset(db_session)
    row = data["rows"][0]
    required = {
        "position_id", "asset", "timeframe", "side",
        "entry_price", "exit_price", "realized_pnl",
        "close_reason", "hold_minutes", "opened_at", "closed_at",
        "quality_score", "grade",
    }
    assert required.issubset(row.keys())
