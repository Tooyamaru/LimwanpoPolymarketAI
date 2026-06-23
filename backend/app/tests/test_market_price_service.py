"""
Market price service tests — Sprint 9.

Tests the orchestration layer: loading active markets, calling the CLOB
client, and saving snapshots. Uses mocked CLOB client and in-memory SQLite.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base
from app.models.market_universe import MarketUniverse
from app.services.clob_client import ClobMarketData
from app.services.market_price_service import MarketPriceService
from app.repositories import market_price_repository as repo


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


def _now():
    return datetime.now(timezone.utc)


async def _insert_universe(
    session,
    condition_id: str,
    status: str = "active",
    asset: str = "BTC",
    timeframe: str = "5m",
) -> MarketUniverse:
    mu = MarketUniverse(
        asset=asset,
        timeframe=timeframe,
        series_slug=f"{asset.lower()}-up-or-down-{timeframe}",
        series_id=None,
        event_id="evt-1",
        condition_id=condition_id,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        question=f"{asset} up or down?",
        start_time=_now(),
        end_time=_now() + timedelta(minutes=5),
        status=status,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(mu)
    await session.flush()
    return mu


def _make_clob_data(condition_id: str = "0xabc") -> ClobMarketData:
    return ClobMarketData(
        condition_id=condition_id,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        yes_bid=0.50,
        yes_ask=0.56,
        yes_mid=0.53,
        no_bid=0.44,
        no_ask=0.50,
        no_mid=0.47,
        spread_yes=0.06,
        spread_no=0.06,
        volume=None,
        liquidity=None,
        active=True,
        closed=False,
    )


def _make_mock_clob(return_value=None, side_effect=None):
    mock = MagicMock()
    mock.get_market = AsyncMock(return_value=return_value, side_effect=side_effect)
    mock.close = AsyncMock()
    return mock


# ── refresh — happy path ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_refresh_saves_snapshot_for_active_market(session):
    mu = await _insert_universe(session, "0xBTC")
    clob = _make_mock_clob(return_value=_make_clob_data("0xBTC"))
    service = MarketPriceService(clob_client=clob)

    result = await service.refresh(session)
    assert result["snapshots_saved"] == 1
    assert result["errors"] == 0


@pytest.mark.anyio
async def test_refresh_returns_summary_dict(session):
    await _insert_universe(session, "0xBTC")
    clob = _make_mock_clob(return_value=_make_clob_data("0xBTC"))
    service = MarketPriceService(clob_client=clob)

    result = await service.refresh(session)
    assert "snapshots_saved" in result
    assert "errors" in result
    assert "markets_polled" in result
    assert "active_count" in result
    assert "duration_ms" in result


@pytest.mark.anyio
async def test_refresh_polls_all_active_markets(session):
    for cid in ["0xBTC", "0xETH", "0xSOL", "0xXRP"]:
        await _insert_universe(session, cid)

    calls = []

    async def fake_get_market(condition_id, yes_token_id=None, no_token_id=None):
        calls.append(condition_id)
        return _make_clob_data(condition_id)

    clob = MagicMock()
    clob.get_market = fake_get_market
    clob.close = AsyncMock()

    service = MarketPriceService(clob_client=clob)
    result = await service.refresh(session)
    assert result["snapshots_saved"] == 4
    assert set(calls) == {"0xBTC", "0xETH", "0xSOL", "0xXRP"}


@pytest.mark.anyio
async def test_refresh_skips_non_active_markets(session):
    await _insert_universe(session, "0xACTIVE", status="active")
    await _insert_universe(session, "0xUPCOMING", status="upcoming")
    await _insert_universe(session, "0xEXPIRED", status="expired")

    calls = []

    async def fake_get_market(condition_id, yes_token_id=None, no_token_id=None):
        calls.append(condition_id)
        return _make_clob_data(condition_id)

    clob = MagicMock()
    clob.get_market = fake_get_market
    clob.close = AsyncMock()

    service = MarketPriceService(clob_client=clob)
    result = await service.refresh(session)
    assert "0xACTIVE" in calls
    assert "0xUPCOMING" not in calls
    assert "0xEXPIRED" not in calls
    assert result["snapshots_saved"] == 1


@pytest.mark.anyio
async def test_refresh_counts_clob_none_as_error(session):
    await _insert_universe(session, "0xNODATA")
    clob = _make_mock_clob(return_value=None)
    service = MarketPriceService(clob_client=clob)

    result = await service.refresh(session)
    assert result["snapshots_saved"] == 0
    assert result["errors"] == 1


@pytest.mark.anyio
async def test_refresh_continues_after_single_error(session):
    await _insert_universe(session, "0xOK")
    await _insert_universe(session, "0xFAIL")

    async def fake_get_market(condition_id, yes_token_id=None, no_token_id=None):
        if condition_id == "0xFAIL":
            raise RuntimeError("CLOB exploded")
        return _make_clob_data(condition_id)

    clob = MagicMock()
    clob.get_market = fake_get_market
    clob.close = AsyncMock()

    service = MarketPriceService(clob_client=clob)
    result = await service.refresh(session)
    assert result["snapshots_saved"] == 1
    assert result["errors"] == 1


@pytest.mark.anyio
async def test_refresh_no_active_markets_returns_zeros(session):
    await _insert_universe(session, "0xUP", status="upcoming")
    clob = _make_mock_clob()
    service = MarketPriceService(clob_client=clob)

    result = await service.refresh(session)
    assert result["snapshots_saved"] == 0
    assert result["markets_polled"] == 0


@pytest.mark.anyio
async def test_refresh_snapshot_stored_in_db(session):
    await _insert_universe(session, "0xSTORED")
    clob = _make_mock_clob(return_value=_make_clob_data("0xSTORED"))
    service = MarketPriceService(clob_client=clob)

    await service.refresh(session)
    snapshots = await repo.get_latest_by_condition(session, "0xSTORED")
    assert len(snapshots) == 1
    assert snapshots[0].yes_mid == pytest.approx(0.53)


@pytest.mark.anyio
async def test_refresh_duration_ms_is_non_negative(session):
    clob = _make_mock_clob()
    service = MarketPriceService(clob_client=clob)
    result = await service.refresh(session)
    assert result["duration_ms"] >= 0


# ── context manager / close ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_service_context_manager():
    async with MarketPriceService() as svc:
        assert svc is not None


@pytest.mark.anyio
async def test_service_close_calls_clob_close():
    clob = _make_mock_clob()
    service = MarketPriceService(clob_client=clob)
    service._owns_client = True
    await service.close()
    clob.close.assert_called_once()
