"""
Market price repository tests — Sprint 9.

Uses an in-memory SQLite database via the standard test fixtures.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.database import Base
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_universe import MarketUniverse
from app.services import market_price_repository as repo


# ── In-memory SQLite session fixture ─────────────────────────────────────────

@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _insert_universe(session, condition_id: str, status: str = "active") -> MarketUniverse:
    mu = MarketUniverse(
        asset="BTC",
        timeframe="5m",
        series_slug="btc-up-or-down-5m",
        series_id=None,
        event_id="999",
        condition_id=condition_id,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        question="BTC up or down?",
        start_time=_now(),
        end_time=_now() + timedelta(minutes=5),
        status=status,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(mu)
    await session.flush()
    return mu


async def _insert_snapshot(
    session,
    condition_id: str = "0xabc",
    yes_mid: float = 0.55,
    no_mid: float = 0.45,
    captured_at: datetime = None,
    universe_id: int = None,
) -> MarketPriceSnapshot:
    return await repo.save_snapshot(
        session,
        market_universe_id=universe_id,
        condition_id=condition_id,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        yes_bid=yes_mid - 0.03,
        yes_ask=yes_mid + 0.03,
        yes_mid=yes_mid,
        no_bid=no_mid - 0.03,
        no_ask=no_mid + 0.03,
        no_mid=no_mid,
        spread_yes=0.06,
        spread_no=0.06,
        volume=None,
        liquidity=None,
        captured_at=captured_at or _now(),
    )


# ── save_snapshot ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_save_snapshot_returns_snapshot(session):
    snap = await _insert_snapshot(session)
    assert snap.id is not None
    assert snap.condition_id == "0xabc"


@pytest.mark.anyio
async def test_save_snapshot_persists_yes_mid(session):
    snap = await _insert_snapshot(session, yes_mid=0.62)
    assert snap.yes_mid == pytest.approx(0.62)


@pytest.mark.anyio
async def test_save_snapshot_persists_no_mid(session):
    snap = await _insert_snapshot(session, no_mid=0.38)
    assert snap.no_mid == pytest.approx(0.38)


@pytest.mark.anyio
async def test_save_snapshot_persists_spread(session):
    snap = await _insert_snapshot(session)
    assert snap.spread_yes == pytest.approx(0.06)
    assert snap.spread_no == pytest.approx(0.06)


@pytest.mark.anyio
async def test_save_snapshot_auto_captured_at(session):
    snap = await repo.save_snapshot(
        session,
        market_universe_id=None,
        condition_id="0xauto",
        yes_token_id=None,
        no_token_id=None,
        yes_bid=None,
        yes_ask=None,
        yes_mid=0.5,
        no_bid=None,
        no_ask=None,
        no_mid=0.5,
        spread_yes=None,
        spread_no=None,
        volume=None,
        liquidity=None,
    )
    assert snap.captured_at is not None


@pytest.mark.anyio
async def test_save_snapshot_with_custom_captured_at(session):
    ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    snap = await _insert_snapshot(session, captured_at=ts)
    assert snap.captured_at == ts


@pytest.mark.anyio
async def test_save_snapshot_with_volume_and_liquidity(session):
    snap = await repo.save_snapshot(
        session,
        market_universe_id=None,
        condition_id="0xvol",
        yes_token_id=None,
        no_token_id=None,
        yes_bid=0.49,
        yes_ask=0.51,
        yes_mid=0.50,
        no_bid=0.49,
        no_ask=0.51,
        no_mid=0.50,
        spread_yes=0.02,
        spread_no=0.02,
        volume=9999.0,
        liquidity=2500.0,
    )
    assert snap.volume == pytest.approx(9999.0)
    assert snap.liquidity == pytest.approx(2500.0)


@pytest.mark.anyio
async def test_save_snapshot_null_bid_ask_allowed(session):
    snap = await repo.save_snapshot(
        session,
        market_universe_id=None,
        condition_id="0xnull",
        yes_token_id=None,
        no_token_id=None,
        yes_bid=None,
        yes_ask=None,
        yes_mid=None,
        no_bid=None,
        no_ask=None,
        no_mid=None,
        spread_yes=None,
        spread_no=None,
        volume=None,
        liquidity=None,
    )
    assert snap.id is not None
    assert snap.yes_bid is None


@pytest.mark.anyio
async def test_save_snapshot_with_universe_id(session):
    mu = await _insert_universe(session, "0xwithuni")
    snap = await _insert_snapshot(session, condition_id="0xwithuni", universe_id=mu.id)
    assert snap.market_universe_id == mu.id


# ── get_latest_snapshot ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_latest_snapshot_returns_newest_first(session):
    t1 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)
    await _insert_snapshot(session, captured_at=t1)
    await _insert_snapshot(session, captured_at=t2)

    results = await repo.get_latest_snapshot(session, limit=10)
    assert len(results) == 2
    assert results[0].captured_at >= results[1].captured_at


@pytest.mark.anyio
async def test_get_latest_snapshot_respects_limit(session):
    for _ in range(5):
        await _insert_snapshot(session)

    results = await repo.get_latest_snapshot(session, limit=3)
    assert len(results) == 3


@pytest.mark.anyio
async def test_get_latest_snapshot_empty_db(session):
    results = await repo.get_latest_snapshot(session)
    assert results == []


# ── get_latest_by_condition ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_latest_by_condition_returns_correct_market(session):
    await _insert_snapshot(session, condition_id="0xAAA", yes_mid=0.60)
    await _insert_snapshot(session, condition_id="0xBBB", yes_mid=0.40)

    results = await repo.get_latest_by_condition(session, "0xAAA")
    assert len(results) == 1
    assert results[0].condition_id == "0xAAA"
    assert results[0].yes_mid == pytest.approx(0.60)


@pytest.mark.anyio
async def test_get_latest_by_condition_returns_newest_first(session):
    t1 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc)
    await _insert_snapshot(session, condition_id="0xAAA", yes_mid=0.50, captured_at=t1)
    await _insert_snapshot(session, condition_id="0xAAA", yes_mid=0.55, captured_at=t2)

    results = await repo.get_latest_by_condition(session, "0xAAA", limit=2)
    assert results[0].captured_at > results[1].captured_at


@pytest.mark.anyio
async def test_get_latest_by_condition_limit_1(session):
    for i in range(3):
        t = datetime(2025, 1, 1, i, 0, tzinfo=timezone.utc)
        await _insert_snapshot(session, condition_id="0xLIM", captured_at=t)

    results = await repo.get_latest_by_condition(session, "0xLIM", limit=1)
    assert len(results) == 1


@pytest.mark.anyio
async def test_get_latest_by_condition_not_found(session):
    results = await repo.get_latest_by_condition(session, "0xNOTFOUND")
    assert results == []


# ── get_latest_active_markets ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_latest_active_markets_returns_one_per_condition(session):
    mu = await _insert_universe(session, "0xACT", status="active")
    t1 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc)
    await _insert_snapshot(session, condition_id="0xACT", captured_at=t1, universe_id=mu.id)
    await _insert_snapshot(session, condition_id="0xACT", captured_at=t2, universe_id=mu.id)

    results = await repo.get_latest_active_markets(session)
    conds = [r.condition_id for r in results]
    assert conds.count("0xACT") == 1


@pytest.mark.anyio
async def test_get_latest_active_markets_excludes_non_active(session):
    mu_active = await _insert_universe(session, "0xACTIVE", status="active")
    mu_upcom = await _insert_universe(session, "0xUPCOMING", status="upcoming")
    await _insert_snapshot(session, condition_id="0xACTIVE", universe_id=mu_active.id)
    await _insert_snapshot(session, condition_id="0xUPCOMING", universe_id=mu_upcom.id)

    results = await repo.get_latest_active_markets(session)
    conds = [r.condition_id for r in results]
    assert "0xACTIVE" in conds
    assert "0xUPCOMING" not in conds


@pytest.mark.anyio
async def test_get_latest_active_markets_empty_when_no_active(session):
    results = await repo.get_latest_active_markets(session)
    assert results == []


@pytest.mark.anyio
async def test_get_latest_active_markets_returns_latest_snapshot(session):
    mu = await _insert_universe(session, "0xLATEST", status="active")
    t_old = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)
    await _insert_snapshot(session, condition_id="0xLATEST", yes_mid=0.40, captured_at=t_old, universe_id=mu.id)
    await _insert_snapshot(session, condition_id="0xLATEST", yes_mid=0.60, captured_at=t_new, universe_id=mu.id)

    results = await repo.get_latest_active_markets(session)
    latest = next(r for r in results if r.condition_id == "0xLATEST")
    assert latest.yes_mid == pytest.approx(0.60)


# ── get_snapshot_count ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_snapshot_count_zero(session):
    count = await repo.get_snapshot_count(session)
    assert count == 0


@pytest.mark.anyio
async def test_get_snapshot_count_after_inserts(session):
    for _ in range(7):
        await _insert_snapshot(session)
    count = await repo.get_snapshot_count(session)
    assert count == 7
