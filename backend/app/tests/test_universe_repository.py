"""
Universe repository tests — Sprint 7.

Uses in-memory SQLite for full isolation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models  # register all models with Base.metadata
from app.core.database import Base
from app.repositories.universe_repository import (
    upsert_universe_market,
    expire_stale_markets,
    get_active_universe,
    get_upcoming_universe,
    get_all_universe,
    get_universe_by_series,
    get_universe_stats,
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


def _future(seconds: int = 3600) -> datetime:
    return _now() + timedelta(seconds=seconds)


def _past(seconds: int = 3600) -> datetime:
    return _now() - timedelta(seconds=seconds)


async def _insert(session, *, condition_id="cid-001", status="active", **kwargs):
    defaults = dict(
        asset="BTC",
        timeframe="5m",
        series_slug="btc-up-or-down-5m",
        series_id="s1",
        event_id="e1",
        condition_id=condition_id,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        question="Will BTC go up?",
        start_time=_now(),
        end_time=_future(),
        status=status,
    )
    defaults.update(kwargs)
    return await upsert_universe_market(session, **defaults)


# ── upsert_universe_market ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_upsert_creates_new_row(db_session):
    m = await _insert(db_session, condition_id="new-001")
    await db_session.commit()
    assert m.id is not None
    assert m.condition_id == "new-001"
    assert m.asset == "BTC"
    assert m.status == "active"


@pytest.mark.anyio
async def test_upsert_returns_existing_and_updates_status(db_session):
    m1 = await _insert(db_session, condition_id="upsert-cid", status="active")
    await db_session.commit()

    m2 = await _insert(db_session, condition_id="upsert-cid", status="expired")
    await db_session.commit()

    assert m1.id == m2.id
    assert m2.status == "expired"


@pytest.mark.anyio
async def test_upsert_different_condition_ids_create_separate_rows(db_session):
    m1 = await _insert(db_session, condition_id="cid-A")
    m2 = await _insert(db_session, condition_id="cid-B")
    await db_session.commit()
    assert m1.id != m2.id


@pytest.mark.anyio
async def test_upsert_stores_all_fields(db_session):
    start = _now()
    end = _future(7200)
    m = await upsert_universe_market(
        db_session,
        asset="ETH",
        timeframe="15m",
        series_slug="eth-up-or-down-15m",
        series_id="series-eth",
        event_id="evt-eth-1",
        condition_id="eth-cid-001",
        yes_token_id="yes-eth",
        no_token_id="no-eth",
        question="Will ETH go up in 15m?",
        start_time=start,
        end_time=end,
        status="upcoming",
    )
    await db_session.commit()

    assert m.asset == "ETH"
    assert m.timeframe == "15m"
    assert m.series_slug == "eth-up-or-down-15m"
    assert m.series_id == "series-eth"
    assert m.event_id == "evt-eth-1"
    assert m.yes_token_id == "yes-eth"
    assert m.no_token_id == "no-eth"
    assert m.question == "Will ETH go up in 15m?"
    assert m.status == "upcoming"


@pytest.mark.anyio
async def test_upsert_updates_end_time(db_session):
    await _insert(db_session, condition_id="cid-endtime", end_time=_future(100))
    await db_session.commit()

    new_end = _future(9999)
    m = await _insert(db_session, condition_id="cid-endtime", end_time=new_end)
    await db_session.commit()
    assert m.end_time == new_end


@pytest.mark.anyio
async def test_upsert_sets_created_and_updated_at(db_session):
    m = await _insert(db_session, condition_id="ts-cid")
    await db_session.commit()
    assert m.created_at is not None
    assert m.updated_at is not None


# ── expire_stale_markets ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_expire_stale_active_market(db_session):
    await _insert(db_session, condition_id="stale-active", status="active", end_time=_past(60))
    await db_session.commit()

    count = await expire_stale_markets(db_session)
    await db_session.commit()
    assert count == 1

    all_rows = await get_all_universe(db_session)
    assert all_rows[0].status == "expired"


@pytest.mark.anyio
async def test_expire_stale_upcoming_market(db_session):
    await _insert(db_session, condition_id="stale-upcoming", status="upcoming", end_time=_past(120))
    await db_session.commit()

    count = await expire_stale_markets(db_session)
    await db_session.commit()
    assert count == 1


@pytest.mark.anyio
async def test_expire_does_not_touch_future_markets(db_session):
    await _insert(db_session, condition_id="future-1", status="active", end_time=_future(999))
    await db_session.commit()

    count = await expire_stale_markets(db_session)
    await db_session.commit()
    assert count == 0


@pytest.mark.anyio
async def test_expire_no_rows_returns_zero(db_session):
    count = await expire_stale_markets(db_session)
    assert count == 0


# ── get_active_universe ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_active_universe_returns_only_active(db_session):
    await _insert(db_session, condition_id="a1", status="active")
    await _insert(db_session, condition_id="a2", status="upcoming")
    await _insert(db_session, condition_id="a3", status="expired")
    await db_session.commit()

    active = await get_active_universe(db_session)
    assert len(active) == 1
    assert active[0].condition_id == "a1"


@pytest.mark.anyio
async def test_get_active_universe_empty(db_session):
    result = await get_active_universe(db_session)
    assert result == []


# ── get_upcoming_universe ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_upcoming_universe_returns_only_upcoming(db_session):
    await _insert(db_session, condition_id="u1", status="upcoming")
    await _insert(db_session, condition_id="u2", status="active")
    await db_session.commit()

    upcoming = await get_upcoming_universe(db_session)
    assert len(upcoming) == 1
    assert upcoming[0].condition_id == "u1"


# ── get_all_universe ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_all_universe_returns_all_rows(db_session):
    for i, status in enumerate(["active", "upcoming", "expired"]):
        await _insert(db_session, condition_id=f"all-{i}", status=status)
    await db_session.commit()

    all_rows = await get_all_universe(db_session)
    assert len(all_rows) == 3


# ── get_universe_by_series ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_universe_by_series_filters_correctly(db_session):
    await _insert(db_session, condition_id="s-btc", series_slug="btc-up-or-down-5m")
    await _insert(db_session, condition_id="s-eth", series_slug="eth-up-or-down-5m")
    await db_session.commit()

    btc_rows = await get_universe_by_series(db_session, "btc-up-or-down-5m")
    assert len(btc_rows) == 1
    assert btc_rows[0].condition_id == "s-btc"


@pytest.mark.anyio
async def test_get_universe_by_series_empty(db_session):
    rows = await get_universe_by_series(db_session, "non-existent-slug")
    assert rows == []


# ── get_universe_stats ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_universe_stats_structure(db_session):
    stats = await get_universe_stats(db_session)
    assert "total" in stats
    assert "by_status" in stats
    assert "by_asset" in stats
    assert "by_timeframe" in stats


@pytest.mark.anyio
async def test_get_universe_stats_empty_db(db_session):
    stats = await get_universe_stats(db_session)
    assert stats["total"] == 0
    assert stats["by_status"]["active"] == 0
    assert stats["by_status"]["upcoming"] == 0
    assert stats["by_status"]["expired"] == 0


@pytest.mark.anyio
async def test_get_universe_stats_counts(db_session):
    await _insert(db_session, condition_id="s1", asset="BTC", timeframe="5m", status="active")
    await _insert(db_session, condition_id="s2", asset="BTC", timeframe="15m", status="upcoming")
    await _insert(db_session, condition_id="s3", asset="ETH", timeframe="5m", status="expired")
    await db_session.commit()

    stats = await get_universe_stats(db_session)
    assert stats["total"] == 3
    assert stats["by_status"]["active"] == 1
    assert stats["by_status"]["upcoming"] == 1
    assert stats["by_status"]["expired"] == 1
    assert stats["by_asset"]["BTC"]["total"] == 2
    assert stats["by_asset"]["ETH"]["total"] == 1
