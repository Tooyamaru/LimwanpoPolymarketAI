"""
Scanner engine tests — Sprint 3.

Tests that the ScannerService correctly orchestrates discovery and persists
results through the repository layer using in-memory SQLite.
"""

import json
import pytest
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models
from app.core.database import Base
from app.services.market_discovery import MarketDiscoveryService
from app.services.scanner import ScannerService
from app.services.scanner_repository import get_scanner_markets, get_scanner_stats

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

MOCK_MARKETS = {
    "data": [
        {
            "condition_id": "0xscan-btc-5m",
            "question": "Will BTC be Up or Down in 5m?",
            "tokens": [
                {"token_id": "a", "outcome": "Yes", "price": 0.65},
                {"token_id": "b", "outcome": "No", "price": 0.35},
            ],
            "liquidity": 5000.0,
            "volume": 2000.0,
            "end_date_iso": None,
        },
        {
            "condition_id": "0xscan-sol-1h",
            "question": "SOL Up or Down in 1H?",
            "tokens": [
                {"token_id": "c", "outcome": "Yes", "price": 0.55},
                {"token_id": "d", "outcome": "No", "price": 0.45},
            ],
            "liquidity": 3000.0,
            "volume": 1000.0,
            "end_date_iso": None,
        },
    ],
    "next_cursor": "",
}


class MockScannerTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(MOCK_MARKETS).encode(),
            headers={"Content-Type": "application/json"},
        )


@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def scanner_with_mock(db_engine, monkeypatch) -> ScannerService:
    """Scanner backed by mock HTTP + in-memory SQLite."""

    mock_client = httpx.AsyncClient(
        base_url="https://clob.polymarket.com",
        transport=MockScannerTransport(),
    )

    original_factory_fn = None

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # Patch get_session_factory to return our test factory
    import app.services.scanner as scanner_module
    monkeypatch.setattr(scanner_module, "get_session_factory", lambda: factory)

    svc = ScannerService()
    svc._discovery._client = mock_client
    return svc


@pytest.mark.anyio
async def test_scanner_run_returns_result(scanner_with_mock: ScannerService) -> None:
    from app.services.market_discovery import DiscoveryResult
    result = await scanner_with_mock.run()
    assert isinstance(result, DiscoveryResult)
    assert result.total_matched == 2


@pytest.mark.anyio
async def test_scanner_persists_markets(scanner_with_mock: ScannerService, db_engine) -> None:
    await scanner_with_mock.run()

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        markets = await get_scanner_markets(session)
    assert len(markets) == 2


@pytest.mark.anyio
async def test_scanner_markets_have_transparency(scanner_with_mock: ScannerService, db_engine) -> None:
    await scanner_with_mock.run()

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        markets = await get_scanner_markets(session)

    for m in markets:
        assert m.raw_title != ""
        assert m.matching_rule != ""
        assert m.detected_asset in {"BTC", "ETH", "SOL", "XRP"}
        assert m.detected_timeframe != ""


@pytest.mark.anyio
async def test_scanner_idempotent_run(scanner_with_mock: ScannerService, db_engine) -> None:
    """Running scanner twice should not double-insert markets."""
    await scanner_with_mock.run()
    await scanner_with_mock.run()

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        markets = await get_scanner_markets(session)
    assert len(markets) == 2
