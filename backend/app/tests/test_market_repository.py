"""
Market repository tests — Sprint 2.

Uses a real async DB session via the test fixtures (in-memory SQLite or
the Replit PostgreSQL). Models must be registered before the session is used.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

import app.models  # ensure models are registered with Base.metadata
from app.core.database import Base
from app.repositories.market_repository import (
    save_market,
    update_market,
    save_snapshot,
    get_active_markets,
    get_latest_snapshots,
)


# ── In-memory SQLite engine for isolated tests ────────────────────────────────

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


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_save_market_creates_row(db_session: AsyncSession) -> None:
    market = await save_market(
        db_session,
        asset="BTC",
        timeframe="5m",
        polymarket_market_id="test-id-001",
        title="Will BTC be above $70k in 5m?",
    )
    await db_session.commit()
    assert market.id is not None
    assert market.asset == "BTC"
    assert market.timeframe == "5m"
    assert market.status == "active"


@pytest.mark.anyio
async def test_save_market_idempotent(db_session: AsyncSession) -> None:
    """Saving the same market_id twice returns the existing record, no duplicate."""
    m1 = await save_market(
        db_session,
        asset="ETH",
        timeframe="15m",
        polymarket_market_id="dupe-id",
        title="ETH 15m market",
    )
    await db_session.commit()

    m2 = await save_market(
        db_session,
        asset="ETH",
        timeframe="15m",
        polymarket_market_id="dupe-id",
        title="ETH 15m market",
    )
    await db_session.commit()

    assert m1.id == m2.id


@pytest.mark.anyio
async def test_save_snapshot(db_session: AsyncSession) -> None:
    market = await save_market(
        db_session,
        asset="SOL",
        timeframe="1H",
        polymarket_market_id="sol-1h-001",
        title="SOL 1H market",
    )
    await db_session.flush()

    snap = await save_snapshot(
        db_session,
        market_id=market.id,
        timestamp=datetime.now(timezone.utc),
        yes_price=0.72,
        no_price=0.28,
        liquidity=50000.0,
        volume=12000.0,
        binance_price=180.0,
    )
    await db_session.commit()

    assert snap.id is not None
    assert snap.market_id == market.id
    assert snap.yes_price == pytest.approx(0.72)
    assert snap.binance_price == pytest.approx(180.0)


@pytest.mark.anyio
async def test_get_active_markets(db_session: AsyncSession) -> None:
    await save_market(
        db_session, asset="BTC", timeframe="5m",
        polymarket_market_id="btc-5m-a", title="BTC 5m A", status="active"
    )
    await save_market(
        db_session, asset="XRP", timeframe="15m",
        polymarket_market_id="xrp-15m-b", title="XRP 15m B", status="closed"
    )
    await db_session.commit()

    active = await get_active_markets(db_session)
    assert len(active) == 1
    assert active[0].asset == "BTC"


@pytest.mark.anyio
async def test_get_latest_snapshots(db_session: AsyncSession) -> None:
    market = await save_market(
        db_session, asset="ETH", timeframe="5m",
        polymarket_market_id="eth-5m-snap", title="ETH 5m"
    )
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(3):
        await save_snapshot(
            db_session,
            market_id=market.id,
            timestamp=now,
            yes_price=0.5 + i * 0.01,
        )
    await db_session.commit()

    snaps = await get_latest_snapshots(db_session, limit=10)
    assert len(snaps) == 3
