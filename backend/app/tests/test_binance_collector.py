"""
Binance Spot Collector tests — Sprint 2.

Uses httpx mock transport to avoid hitting the live API during tests.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.collector.binance_spot import BinanceSpotCollector, BinanceSpotData, SYMBOLS


MOCK_BINANCE_RESPONSE = [
    {
        "symbol": "BTCUSDT",
        "lastPrice": "65000.00",
        "bidPrice": "64998.00",
        "askPrice": "65002.00",
        "volume": "1234.56",
    },
    {
        "symbol": "ETHUSDT",
        "lastPrice": "3500.00",
        "bidPrice": "3499.00",
        "askPrice": "3501.00",
        "volume": "9876.54",
    },
    {
        "symbol": "SOLUSDT",
        "lastPrice": "180.00",
        "bidPrice": "179.95",
        "askPrice": "180.05",
        "volume": "500000.00",
    },
    {
        "symbol": "XRPUSDT",
        "lastPrice": "0.62",
        "bidPrice": "0.619",
        "askPrice": "0.621",
        "volume": "9000000.00",
    },
]


class MockTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(MOCK_BINANCE_RESPONSE).encode(),
            headers={"Content-Type": "application/json"},
        )


@pytest.fixture
def collector_with_mock() -> BinanceSpotCollector:
    collector = BinanceSpotCollector()
    collector._client = httpx.AsyncClient(
        base_url="https://api.binance.com",
        transport=MockTransport(),
    )
    return collector


@pytest.mark.anyio
async def test_fetch_returns_list(collector_with_mock: BinanceSpotCollector) -> None:
    results = await collector_with_mock.fetch()
    assert isinstance(results, list)
    assert len(results) == 4


@pytest.mark.anyio
async def test_fetch_returns_correct_types(collector_with_mock: BinanceSpotCollector) -> None:
    results = await collector_with_mock.fetch()
    for item in results:
        assert isinstance(item, BinanceSpotData)
        assert isinstance(item.last_price, float)
        assert isinstance(item.bid, float)
        assert isinstance(item.ask, float)
        assert isinstance(item.volume, float)
        assert isinstance(item.timestamp, datetime)


@pytest.mark.anyio
async def test_fetch_correct_symbols(collector_with_mock: BinanceSpotCollector) -> None:
    results = await collector_with_mock.fetch()
    returned_symbols = {r.symbol for r in results}
    assert returned_symbols == {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"}


@pytest.mark.anyio
async def test_fetch_correct_values(collector_with_mock: BinanceSpotCollector) -> None:
    results = await collector_with_mock.fetch()
    btc = next(r for r in results if r.symbol == "BTCUSDT")
    assert btc.last_price == 65000.00
    assert btc.bid == 64998.00
    assert btc.ask == 65002.00
    assert btc.volume == 1234.56


@pytest.mark.anyio
async def test_collector_default_symbols() -> None:
    collector = BinanceSpotCollector()
    assert set(collector.symbols) == set(SYMBOLS)
    await collector.close()


@pytest.mark.anyio
async def test_close_cleans_up(collector_with_mock: BinanceSpotCollector) -> None:
    await collector_with_mock.close()
    assert collector_with_mock._client is None
