"""
Portfolio service tests — Layer 10: Portfolio Reporting.

Uses in-memory SQLite (aiosqlite) for full isolation.
Tests the PortfolioService class, which delegates to portfolio_repository.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models
from app.core.database import Base
from app.services.portfolio_service import PortfolioService
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


@pytest.fixture
def service() -> PortfolioService:
    return PortfolioService()


# ── get_portfolio_summary ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_portfolio_summary_empty(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_portfolio_summary(db_session)
    assert result["total_positions"] == 0
    assert result["total_orders"] == 0
    assert result["approved_decisions"] == 0
    assert result["blocked_decisions"] == 0


@pytest.mark.anyio
async def test_service_portfolio_summary_keys_present(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_portfolio_summary(db_session)
    expected_keys = {
        "total_positions", "open_positions", "closed_positions",
        "total_orders", "executed_orders",
        "approved_decisions", "blocked_decisions",
    }
    assert set(result.keys()) == expected_keys


# ── get_position_summary ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_position_summary_empty(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_position_summary(db_session)
    assert result["total_positions"] == 0
    assert result["by_asset"] == {}
    assert result["by_side"] == {}


@pytest.mark.anyio
async def test_service_position_summary_with_data(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        Position(
            order_id=10, condition_id="c1", asset="SOL", timeframe="5m",
            side="YES", quantity=1.0, entry_price=0.50,
            status="OPEN", opened_at=_now(),
        ),
        Position(
            order_id=11, condition_id="c2", asset="XRP", timeframe="15m",
            side="NO", quantity=1.0, entry_price=0.50,
            status="OPEN", opened_at=_now(),
        ),
    ])
    await db_session.commit()

    result = await service.get_position_summary(db_session)
    assert result["total_positions"] == 2
    assert result["open_positions"] == 2
    assert result["by_asset"]["SOL"] == 1
    assert result["by_asset"]["XRP"] == 1
    assert result["by_side"]["YES"] == 1
    assert result["by_side"]["NO"] == 1


# ── get_order_summary ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_order_summary_empty(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_order_summary(db_session)
    assert result["total_orders"] == 0
    assert result["filled_orders"] == 0
    assert result["by_asset"] == {}


@pytest.mark.anyio
async def test_service_order_summary_keys_present(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_order_summary(db_session)
    expected_keys = {
        "total_orders", "filled_orders", "pending_orders",
        "by_asset", "by_side",
    }
    assert set(result.keys()) == expected_keys


# ── get_risk_summary ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_risk_summary_empty(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_risk_summary(db_session)
    assert result["total_checked"] == 0
    assert result["block_rate_pct"] == 0.0
    assert result["by_reason"] == {}


@pytest.mark.anyio
async def test_service_risk_summary_with_blocks(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        RiskEvent(
            decision_id=1, condition_id="c1", asset="BTC", timeframe="5m",
            result="ALLOW", checked_at=_now(),
            open_positions_count=0, daily_loss=0.0, daily_trades=0,
        ),
        RiskEvent(
            decision_id=2, condition_id="c2", asset="ETH", timeframe="5m",
            result="BLOCK", reason="MAX_DAILY_TRADES", checked_at=_now(),
            open_positions_count=0, daily_loss=0.0, daily_trades=20,
        ),
    ])
    await db_session.commit()

    result = await service.get_risk_summary(db_session)
    assert result["total_checked"] == 2
    assert result["allowed"] == 1
    assert result["blocked"] == 1
    assert result["block_rate_pct"] == 50.0
    assert result["by_reason"]["MAX_DAILY_TRADES"] == 1


# ── get_pnl_summary ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_pnl_summary_empty(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_pnl_summary(db_session)
    assert result["open_positions"] == 0
    assert result["total_unrealized_pnl"] == 0.0
    assert result["total_realized_pnl"] == 0.0


@pytest.mark.anyio
async def test_service_pnl_summary_keys_present(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    result = await service.get_pnl_summary(db_session)
    expected_keys = {
        "open_positions", "total_unrealized_pnl", "average_unrealized_pnl",
        "closed_positions", "total_realized_pnl",
    }
    assert set(result.keys()) == expected_keys


@pytest.mark.anyio
async def test_service_pnl_summary_with_positions(
    service: PortfolioService, db_session: AsyncSession
) -> None:
    db_session.add_all([
        Position(
            order_id=20, condition_id="c1", asset="BTC", timeframe="5m",
            side="YES", quantity=1.0, entry_price=0.48,
            status="OPEN", unrealized_pnl=0.02, opened_at=_now(),
        ),
        Position(
            order_id=21, condition_id="c2", asset="ETH", timeframe="1H",
            side="NO", quantity=1.0, entry_price=0.52,
            status="CLOSED", realized_pnl=0.03, opened_at=_now(),
        ),
    ])
    await db_session.commit()

    result = await service.get_pnl_summary(db_session)
    assert result["open_positions"] == 1
    assert abs(result["total_unrealized_pnl"] - 0.02) < 1e-6
    assert result["closed_positions"] == 1
    assert abs(result["total_realized_pnl"] - 0.03) < 1e-6
