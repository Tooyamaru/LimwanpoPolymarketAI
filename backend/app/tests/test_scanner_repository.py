"""
Scanner repository tests — Sprint 3.

Uses in-memory SQLite (aiosqlite) for full isolation.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models  # registers all models with Base.metadata
from app.core.database import Base
from app.repositories.scanner_repository import (
    save_scanner_market,
    mark_stale_markets,
    get_scanner_markets,
    get_scanner_stats,
)

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


async def _create_market(session, market_id="test-001", asset="BTC", timeframe="5m"):
    return await save_scanner_market(
        session,
        asset=asset,
        timeframe=timeframe,
        market_id=market_id,
        health_status="active",
        created_at=_now(),
        raw_title=f"{asset} price in {timeframe}?",
        matching_rule=f"exact_{asset} + tf_{timeframe}",
        detected_asset=asset,
        detected_timeframe=timeframe,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_save_scanner_market_creates_row(db_session: AsyncSession) -> None:
    m = await _create_market(db_session)
    await db_session.commit()
    assert m.id is not None
    assert m.asset == "BTC"
    assert m.health_status == "active"


@pytest.mark.anyio
async def test_save_scanner_market_idempotent(db_session: AsyncSession) -> None:
    m1 = await _create_market(db_session, market_id="dupe-001")
    await db_session.commit()

    m2 = await _create_market(db_session, market_id="dupe-001")
    await db_session.commit()

    assert m1.id == m2.id


@pytest.mark.anyio
async def test_save_scanner_market_transparency(db_session: AsyncSession) -> None:
    m = await save_scanner_market(
        db_session,
        asset="ETH",
        timeframe="15m",
        market_id="eth-trans-001",
        health_status="active",
        created_at=_now(),
        raw_title="ETH price in 15 minutes?",
        matching_rule="exact_ETH + tf_15m",
        detected_asset="ETH",
        detected_timeframe="15 min",
    )
    await db_session.commit()
    assert m.raw_title == "ETH price in 15 minutes?"
    assert m.matching_rule == "exact_ETH + tf_15m"
    assert m.detected_asset == "ETH"
    assert m.detected_timeframe == "15 min"


@pytest.mark.anyio
async def test_get_scanner_markets_all(db_session: AsyncSession) -> None:
    await _create_market(db_session, "m1", "BTC", "5m")
    await _create_market(db_session, "m2", "ETH", "15m")
    await db_session.commit()
    markets = await get_scanner_markets(db_session)
    assert len(markets) == 2


@pytest.mark.anyio
async def test_get_scanner_markets_filtered(db_session: AsyncSession) -> None:
    await _create_market(db_session, "m1", "BTC", "5m")
    m2 = await _create_market(db_session, "m2", "ETH", "15m")
    m2.health_status = "stale"
    await db_session.commit()

    active = await get_scanner_markets(db_session, health_status="active")
    assert len(active) == 1
    assert active[0].asset == "BTC"


@pytest.mark.anyio
async def test_mark_stale_markets(db_session: AsyncSession) -> None:
    m1 = await _create_market(db_session, "market-keep", "BTC", "5m")
    m2 = await _create_market(db_session, "market-stale", "ETH", "15m")
    await db_session.commit()

    # Only market-keep is in the active set
    count = await mark_stale_markets(db_session, active_ids={"market-keep"})
    await db_session.commit()

    assert count == 1
    assert m2.health_status == "stale"
    assert m1.health_status == "active"


@pytest.mark.anyio
async def test_scanner_stats(db_session: AsyncSession) -> None:
    await _create_market(db_session, "btc-5m", "BTC", "5m")
    await _create_market(db_session, "eth-15m", "ETH", "15m")
    m3 = await _create_market(db_session, "sol-1h", "SOL", "1H")
    m3.health_status = "stale"
    await db_session.commit()

    stats = await get_scanner_stats(db_session)
    assert stats["total"] == 3
    assert stats["active"] == 2
    assert stats["stale"] == 1
    assert stats["by_asset"]["BTC"] == 1
    assert stats["by_asset"]["ETH"] == 1
    assert stats["by_asset"]["SOL"] == 1
    assert stats["by_asset"]["XRP"] == 0


@pytest.mark.anyio
async def test_scanner_stats_empty(db_session: AsyncSession) -> None:
    stats = await get_scanner_stats(db_session)
    assert stats["total"] == 0
    assert stats["active"] == 0
