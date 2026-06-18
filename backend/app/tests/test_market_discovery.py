"""
Market discovery engine tests — Sprint 3.

Uses httpx mock transport to avoid live Polymarket API calls.
"""

import json
import pytest

import httpx

from app.services.market_discovery import (
    MarketDiscoveryService,
    DiscoveryResult,
    MatchedMarket,
    _match_asset,
    _match_timeframe,
)


# ── Matching helper unit tests ────────────────────────────────────────────────

def test_match_asset_btc():
    result = _match_asset("Will BTC be above $70k?")
    assert result is not None
    rule, asset = result
    assert asset == "BTC"
    assert "BTC" in rule


def test_match_asset_eth():
    result = _match_asset("ETH price above $4,000 in 15m?")
    assert result is not None
    _, asset = result
    assert asset == "ETH"


def test_match_asset_sol():
    result = _match_asset("Solana up 10% today?")
    assert result is not None
    _, asset = result
    assert asset == "SOL"


def test_match_asset_xrp():
    result = _match_asset("XRP vs USD 1 hour market")
    assert result is not None
    _, asset = result
    assert asset == "XRP"


def test_match_asset_no_match():
    assert _match_asset("Will the Fed cut rates?") is None


def test_match_timeframe_5m():
    result = _match_timeframe("BTC above $65k in 5m?")
    assert result is not None
    _, _, normalised = result
    assert normalised == "5m"


def test_match_timeframe_15m():
    result = _match_timeframe("ETH price in 15 minutes")
    assert result is not None
    _, _, normalised = result
    assert normalised == "15m"


def test_match_timeframe_1H():
    result = _match_timeframe("SOL above $200 in 1 hour?")
    assert result is not None
    _, _, normalised = result
    assert normalised == "1H"


def test_match_timeframe_1H_abbr():
    result = _match_timeframe("BTC price in 1H?")
    assert result is not None
    _, _, normalised = result
    assert normalised == "1H"


def test_match_timeframe_no_match():
    assert _match_timeframe("Will Federer win today?") is None


# ── Discovery service integration tests (mocked HTTP) ────────────────────────

MOCK_PAGE_1 = {
    "data": [
        {
            "condition_id": "0xbtc5m001",
            "question": "Will BTC be above $70k in 5m?",
            "tokens": [
                {"token_id": "a", "outcome": "Yes", "price": 0.72},
                {"token_id": "b", "outcome": "No", "price": 0.28},
            ],
            "liquidity": 10000.0,
            "volume": 5000.0,
            "end_date_iso": None,
        },
        {
            "condition_id": "0xeth15m001",
            "question": "ETH price above $4,000 in 15 minutes?",
            "tokens": [
                {"token_id": "c", "outcome": "Yes", "price": 0.45},
                {"token_id": "d", "outcome": "No", "price": 0.55},
            ],
            "liquidity": 8000.0,
            "volume": 3000.0,
            "end_date_iso": None,
        },
        {
            "condition_id": "0xnomatch001",
            "question": "Will the US CPI beat expectations?",
            "tokens": [],
            "liquidity": 0.0,
            "volume": 0.0,
            "end_date_iso": None,
        },
    ],
    "next_cursor": "",
}


class MockDiscoveryTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(MOCK_PAGE_1).encode(),
            headers={"Content-Type": "application/json"},
        )


@pytest.fixture
def discovery_with_mock() -> MarketDiscoveryService:
    svc = MarketDiscoveryService()
    svc._client = httpx.AsyncClient(
        base_url="https://clob.polymarket.com",
        transport=MockDiscoveryTransport(),
    )
    return svc


@pytest.mark.anyio
async def test_discover_returns_result(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    assert isinstance(result, DiscoveryResult)


@pytest.mark.anyio
async def test_discover_total_scanned(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    assert result.total_scanned == 3  # 3 raw records in mock page


@pytest.mark.anyio
async def test_discover_matched_count(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    assert result.total_matched == 2  # BTC 5m + ETH 15m; CPI has no match


@pytest.mark.anyio
async def test_discover_asset_counts(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    assert result.btc_count == 1
    assert result.eth_count == 1
    assert result.sol_count == 0
    assert result.xrp_count == 0


@pytest.mark.anyio
async def test_discover_transparency_fields(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    btc_market = next(m for m in result.matched_markets if m.asset == "BTC")
    assert btc_market.raw_title == "Will BTC be above $70k in 5m?"
    assert "BTC" in btc_market.matching_rule
    assert btc_market.detected_asset == "BTC"
    assert btc_market.timeframe == "5m"
    assert btc_market.matching_rule != ""  # must not be empty


@pytest.mark.anyio
async def test_discover_prices_parsed(discovery_with_mock: MarketDiscoveryService) -> None:
    result = await discovery_with_mock.discover()
    btc = next(m for m in result.matched_markets if m.asset == "BTC")
    assert btc.yes_price == pytest.approx(0.72)
    assert btc.no_price == pytest.approx(0.28)
