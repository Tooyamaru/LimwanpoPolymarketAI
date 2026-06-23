"""
Portfolio repository tests — Layer 10: Portfolio Reporting.

Uses in-memory SQLite (aiosqlite) for full isolation.
Tests all five read-only aggregation functions against known fixture data.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models  # registers all models with Base.metadata
from app.core.database import Base
from app.repositories.portfolio_repository import (
    get_portfolio_summary,
    get_position_summary,
    get_order_summary,
    get_risk_summary,
    get_pnl_summary,
)
from app.models.position import Position
from app.models.order import Order
from app.models.trade_decision import TradeDecision
from app.models.risk_event import RiskEvent

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_position(
    order_id: int,
    condition_id: str = "cond-001",
    asset: str = "BTC",
    timeframe: str = "5m",
    side: str = "YES",
    quantity: float = 1.0,
    entry_price: float = 0.50,
    status: str = "OPEN",
    unrealized_pnl: float | None = None,
    realized_pnl: float | None = None,
) -> Position:
    return Position(
        order_id=order_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        status=status,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        opened_at=_now(),
    )


def _make_order(
    decision_id: int,
    condition_id: str = "cond-001",
    asset: str = "BTC",
    timeframe: str = "5m",
    side: str = "YES",
    status: str = "FILLED",
    filled_price: float = 0.50,
) -> Order:
    return Order(
        decision_id=decision_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        side=side,
        quantity=1.0,
        order_type="MARKET",
        status=status,
        filled_price=filled_price,
        created_at=_now(),
    )


def _make_decision(
    condition_id: str = "cond-001",
    asset: str = "BTC",
    timeframe: str = "5m",
    decision: str = "OPEN_LONG_YES",
    status: str = "EXECUTED",
    score: float = 55.0,
) -> TradeDecision:
    return TradeDecision(
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        decision=decision,
        status=status,
        opportunity_score=score,
        direction="BUY_YES",
        decided_at=_now(),
    )


def _make_risk_event(
    decision_id: int,
    condition_id: str = "cond-001",
    asset: str = "BTC",
    timeframe: str = "5m",
    result: str = "ALLOW",
    reason: str | None = None,
) -> RiskEvent:
    return RiskEvent(
        decision_id=decision_id,
        condition_id=condition_id,
        asset=asset,
        timeframe=timeframe,
        result=result,
        reason=reason,
        open_positions_count=0,
        daily_loss=0.0,
        daily_trades=0,
        checked_at=_now(),
    )


# ── get_portfolio_summary ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_summary_empty(db_session: AsyncSession) -> None:
    summary = await get_portfolio_summary(db_session)
    assert summary["total_positions"] == 0
    assert summary["open_positions"] == 0
    assert summary["closed_positions"] == 0
    assert summary["total_orders"] == 0
    assert summary["executed_orders"] == 0
    assert summary["approved_decisions"] == 0
    assert summary["blocked_decisions"] == 0


@pytest.mark.anyio
async def test_portfolio_summary_with_data(db_session: AsyncSession) -> None:
    td1 = _make_decision(condition_id="c1", status="EXECUTED")
    td2 = _make_decision(condition_id="c2", status="BLOCKED")
    td3 = _make_decision(condition_id="c3", status="RISK_APPROVED")
    db_session.add_all([td1, td2, td3])
    await db_session.flush()

    o1 = _make_order(decision_id=td1.id, condition_id="c1", status="FILLED")
    o2 = _make_order(decision_id=td3.id, condition_id="c3", status="PENDING")
    db_session.add_all([o1, o2])
    await db_session.flush()

    p1 = _make_position(order_id=o1.id, condition_id="c1", status="OPEN")
    p2 = _make_position(order_id=o2.id, condition_id="c3", status="CLOSED")
    db_session.add_all([p1, p2])
    await db_session.commit()

    summary = await get_portfolio_summary(db_session)
    assert summary["total_positions"] == 2
    assert summary["open_positions"] == 1
    assert summary["closed_positions"] == 1
    assert summary["total_orders"] == 2
    assert summary["executed_orders"] == 1
    assert summary["approved_decisions"] == 2  # RISK_APPROVED + EXECUTED
    assert summary["blocked_decisions"] == 1


# ── get_position_summary ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_position_summary_empty(db_session: AsyncSession) -> None:
    summary = await get_position_summary(db_session)
    assert summary["total_positions"] == 0
    assert summary["open_positions"] == 0
    assert summary["closed_positions"] == 0
    assert summary["by_asset"] == {}
    assert summary["by_side"] == {}


@pytest.mark.anyio
async def test_position_summary_by_asset_and_side(db_session: AsyncSession) -> None:
    db_session.add_all([
        _make_position(order_id=1, condition_id="c1", asset="BTC", side="YES", status="OPEN"),
        _make_position(order_id=2, condition_id="c2", asset="BTC", side="NO", status="OPEN"),
        _make_position(order_id=3, condition_id="c3", asset="ETH", side="YES", status="CLOSED"),
    ])
    await db_session.commit()

    summary = await get_position_summary(db_session)
    assert summary["total_positions"] == 3
    assert summary["open_positions"] == 2
    assert summary["closed_positions"] == 1
    assert summary["by_asset"]["BTC"] == 2
    assert summary["by_asset"]["ETH"] == 1
    assert summary["by_side"]["YES"] == 2
    assert summary["by_side"]["NO"] == 1


# ── get_order_summary ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_order_summary_empty(db_session: AsyncSession) -> None:
    summary = await get_order_summary(db_session)
    assert summary["total_orders"] == 0
    assert summary["filled_orders"] == 0
    assert summary["pending_orders"] == 0
    assert summary["by_asset"] == {}
    assert summary["by_side"] == {}


@pytest.mark.anyio
async def test_order_summary_with_data(db_session: AsyncSession) -> None:
    db_session.add_all([
        _make_order(decision_id=1, condition_id="c1", asset="BTC", side="YES", status="FILLED"),
        _make_order(decision_id=2, condition_id="c2", asset="ETH", side="NO", status="FILLED"),
        _make_order(decision_id=3, condition_id="c3", asset="BTC", side="YES", status="PENDING"),
    ])
    await db_session.commit()

    summary = await get_order_summary(db_session)
    assert summary["total_orders"] == 3
    assert summary["filled_orders"] == 2
    assert summary["pending_orders"] == 1
    assert summary["by_asset"]["BTC"] == 2
    assert summary["by_asset"]["ETH"] == 1
    assert summary["by_side"]["YES"] == 2
    assert summary["by_side"]["NO"] == 1


# ── get_risk_summary ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_risk_summary_empty(db_session: AsyncSession) -> None:
    summary = await get_risk_summary(db_session)
    assert summary["total_checked"] == 0
    assert summary["allowed"] == 0
    assert summary["blocked"] == 0
    assert summary["block_rate_pct"] == 0.0
    assert summary["by_reason"] == {}


@pytest.mark.anyio
async def test_risk_summary_block_rate(db_session: AsyncSession) -> None:
    db_session.add_all([
        _make_risk_event(decision_id=1, condition_id="c1", result="ALLOW"),
        _make_risk_event(decision_id=2, condition_id="c2", result="ALLOW"),
        _make_risk_event(decision_id=3, condition_id="c3", result="BLOCK", reason="MAX_OPEN_POSITIONS"),
        _make_risk_event(decision_id=4, condition_id="c4", result="BLOCK", reason="DUPLICATE_POSITION"),
    ])
    await db_session.commit()

    summary = await get_risk_summary(db_session)
    assert summary["total_checked"] == 4
    assert summary["allowed"] == 2
    assert summary["blocked"] == 2
    assert summary["block_rate_pct"] == 50.0
    assert summary["by_reason"]["MAX_OPEN_POSITIONS"] == 1
    assert summary["by_reason"]["DUPLICATE_POSITION"] == 1


# ── get_pnl_summary ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pnl_summary_empty(db_session: AsyncSession) -> None:
    summary = await get_pnl_summary(db_session)
    assert summary["open_positions"] == 0
    assert summary["total_unrealized_pnl"] == 0.0
    assert summary["average_unrealized_pnl"] == 0.0
    assert summary["closed_positions"] == 0
    assert summary["total_realized_pnl"] == 0.0


@pytest.mark.anyio
async def test_pnl_summary_open_positions(db_session: AsyncSession) -> None:
    db_session.add_all([
        _make_position(order_id=1, condition_id="c1", status="OPEN", unrealized_pnl=0.10),
        _make_position(order_id=2, condition_id="c2", status="OPEN", unrealized_pnl=-0.05),
        _make_position(order_id=3, condition_id="c3", status="CLOSED", realized_pnl=0.20),
    ])
    await db_session.commit()

    summary = await get_pnl_summary(db_session)
    assert summary["open_positions"] == 2
    assert abs(summary["total_unrealized_pnl"] - 0.05) < 1e-6
    assert abs(summary["average_unrealized_pnl"] - 0.025) < 1e-6
    assert summary["closed_positions"] == 1
    assert abs(summary["total_realized_pnl"] - 0.20) < 1e-6


@pytest.mark.anyio
async def test_pnl_summary_null_pnl_excluded(db_session: AsyncSession) -> None:
    db_session.add_all([
        _make_position(order_id=1, condition_id="c1", status="OPEN", unrealized_pnl=None),
        _make_position(order_id=2, condition_id="c2", status="OPEN", unrealized_pnl=0.08),
    ])
    await db_session.commit()

    summary = await get_pnl_summary(db_session)
    assert summary["open_positions"] == 1
    assert abs(summary["total_unrealized_pnl"] - 0.08) < 1e-6
