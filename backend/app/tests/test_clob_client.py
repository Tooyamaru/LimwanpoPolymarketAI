"""
CLOB client tests — Sprint 9.

Uses unittest.mock to intercept httpx calls — no real network needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.clob_client import ClobClient, ClobMarketData, OrderBookSide


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_market_response(
    condition_id: str = "0xabc",
    active: bool = True,
    closed: bool = False,
    yes_price: float = 0.55,
    no_price: float = 0.45,
    volume: float = None,
    liquidity: float = None,
    yes_token_id: str = "yes-token-123",
    no_token_id: str = "no-token-456",
) -> dict:
    return {
        "condition_id": condition_id,
        "active": active,
        "closed": closed,
        "volume": volume,
        "liquidity": liquidity,
        "tokens": [
            {"token_id": yes_token_id, "outcome": "Up", "price": yes_price, "winner": False},
            {"token_id": no_token_id, "outcome": "Down", "price": no_price, "winner": False},
        ],
    }


def _make_book_response(best_bid: str = "0.50", best_ask: str = "0.56") -> dict:
    # Real CLOB API: bids ASCENDING (lowest first, best bid = last element)
    #                asks DESCENDING (highest first, best ask = last element)
    return {
        "bids": [{"price": "0.40", "size": "200"}, {"price": best_bid, "size": "100"}],
        "asks": [{"price": "0.70", "size": "200"}, {"price": best_ask, "size": "100"}],
        "last_trade_price": None,
    }


def _mock_http_client(market_resp: dict, book_resp: dict):
    """Return a mock httpx.AsyncClient that answers market and book requests."""
    mock_client = MagicMock()

    async def fake_get(path, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "/book" in path:
            resp.json = MagicMock(return_value=book_resp)
        else:
            resp.json = MagicMock(return_value=market_resp)
        return resp

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()
    return mock_client


# ── OrderBookSide dataclass ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_order_book_side_attributes():
    side = OrderBookSide(best_bid=0.50, best_ask=0.56)
    assert side.best_bid == 0.50
    assert side.best_ask == 0.56


@pytest.mark.anyio
async def test_order_book_side_none_values():
    side = OrderBookSide(best_bid=None, best_ask=None)
    assert side.best_bid is None
    assert side.best_ask is None


# ── ClobMarketData dataclass ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_clob_market_data_fields():
    data = ClobMarketData(
        condition_id="0xabc",
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
    assert data.condition_id == "0xabc"
    assert data.yes_mid == 0.53
    assert data.active is True
    assert data.closed is False


# ── _fetch_order_book ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_order_book_returns_best_bid_ask():
    client = ClobClient()
    client._client = _mock_http_client(
        _make_market_response(), _make_book_response("0.52", "0.58")
    )
    result = await client._fetch_order_book("some-token-id")
    assert result.best_bid == 0.52
    assert result.best_ask == 0.58
    await client.close()


@pytest.mark.anyio
async def test_fetch_order_book_empty_bids():
    mock_client = MagicMock()

    async def fake_get(path, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"bids": [], "asks": [{"price": "0.60", "size": "10"}]})
        return resp

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    client = ClobClient()
    client._client = mock_client
    result = await client._fetch_order_book("tok")
    assert result.best_bid is None
    assert result.best_ask == 0.60
    await client.close()


@pytest.mark.anyio
async def test_fetch_order_book_empty_asks():
    mock_client = MagicMock()

    async def fake_get(path, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"bids": [{"price": "0.40", "size": "10"}], "asks": []})
        return resp

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    client = ClobClient()
    client._client = mock_client
    result = await client._fetch_order_book("tok")
    assert result.best_bid == 0.40
    assert result.best_ask is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_order_book_non_dict_response():
    mock_client = MagicMock()

    async def fake_get(path, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=None)
        return resp

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    client = ClobClient()
    client._client = mock_client
    result = await client._fetch_order_book("tok")
    assert result.best_bid is None
    assert result.best_ask is None
    await client.close()


# ── get_market — happy path ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_market_returns_data():
    market_resp = _make_market_response(
        condition_id="0xdef",
        yes_price=0.55,
        no_price=0.45,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
    )
    book_resp = _make_book_response("0.50", "0.56")

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xdef", "yes-tok", "no-tok")
    assert data is not None
    assert data.condition_id == "0xdef"
    assert data.yes_token_id == "yes-tok"
    assert data.no_token_id == "no-tok"
    assert data.active is True
    assert data.closed is False
    await client.close()


@pytest.mark.anyio
async def test_get_market_computes_yes_mid():
    market_resp = _make_market_response()
    book_resp = _make_book_response("0.48", "0.54")

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.yes_mid == pytest.approx(0.51, abs=1e-5)
    await client.close()


@pytest.mark.anyio
async def test_get_market_computes_no_mid():
    market_resp = _make_market_response()
    book_resp = _make_book_response("0.48", "0.54")

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.no_mid is not None
    await client.close()


@pytest.mark.anyio
async def test_get_market_computes_spread_yes():
    market_resp = _make_market_response()
    book_resp = _make_book_response("0.48", "0.54")

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.spread_yes == pytest.approx(0.06, abs=1e-5)
    await client.close()


@pytest.mark.anyio
async def test_get_market_volume_liquidity_populated():
    market_resp = _make_market_response(volume=5000.0, liquidity=1200.0)
    book_resp = _make_book_response()

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.volume == 5000.0
    assert data.liquidity == 1200.0
    await client.close()


@pytest.mark.anyio
async def test_get_market_volume_none_when_api_returns_null():
    market_resp = _make_market_response(volume=None, liquidity=None)
    book_resp = _make_book_response()

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.volume is None
    assert data.liquidity is None
    await client.close()


@pytest.mark.anyio
async def test_get_market_mid_is_none_when_book_empty():
    """14A1: mid = (bid+ask)/2 only. When book is empty, mid must be None — no fallback."""
    market_resp = _make_market_response(yes_price=0.62, no_price=0.38)
    empty_book = {"bids": [], "asks": []}

    client = ClobClient()
    client._client = _mock_http_client(market_resp, empty_book)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    # With an empty order book there is no valid bid or ask, so mid must be None.
    assert data.yes_mid is None
    assert data.no_mid is None
    await client.close()


@pytest.mark.anyio
async def test_get_market_returns_none_on_non_dict_response():
    mock_client = MagicMock()

    async def fake_get(path, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=None)
        return resp

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    client = ClobClient()
    client._client = mock_client

    data = await client.get_market("0xabc", "yes", "no")
    assert data is None
    await client.close()


@pytest.mark.anyio
async def test_get_market_active_false():
    market_resp = _make_market_response(active=False)
    book_resp = _make_book_response()

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.active is False
    await client.close()


@pytest.mark.anyio
async def test_get_market_closed_true():
    market_resp = _make_market_response(active=False, closed=True)
    book_resp = _make_book_response()

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.closed is True
    await client.close()


@pytest.mark.anyio
async def test_get_market_infers_token_ids_from_market_response():
    """If yes/no token IDs not passed, they are inferred from tokens[] outcomes."""
    market_resp = _make_market_response(
        yes_token_id="inferred-yes",
        no_token_id="inferred-no",
    )
    book_resp = _make_book_response()

    client = ClobClient()
    client._client = _mock_http_client(market_resp, book_resp)

    data = await client.get_market("0xabc")
    assert data is not None
    assert data.yes_token_id == "inferred-yes"
    assert data.no_token_id == "inferred-no"
    await client.close()


@pytest.mark.anyio
async def test_get_market_spread_none_when_one_side_missing():
    market_resp = _make_market_response()
    partial_book = {"bids": [{"price": "0.50", "size": "100"}], "asks": []}

    client = ClobClient()
    client._client = _mock_http_client(market_resp, partial_book)

    data = await client.get_market("0xabc", "yes-token-123", "no-token-456")
    assert data is not None
    assert data.spread_yes is None
    await client.close()


# ── Context manager ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_clob_client_context_manager():
    async with ClobClient() as client:
        assert client is not None


@pytest.mark.anyio
async def test_clob_client_close_idempotent():
    client = ClobClient()
    await client.close()
    await client.close()


# ── Retry on HTTP error ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_json_returns_none_after_all_retries_fail():
    import httpx

    mock_client = MagicMock()
    call_count = 0

    async def fake_get(path, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.RequestError("connection refused")

    mock_client.get = fake_get
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    client = ClobClient()
    client._client = mock_client

    with patch("app.services.clob_client.asyncio.sleep", new_callable=AsyncMock):
        result = await client._get_json("/markets/0xabc")
    assert result is None
    assert call_count == 3
    await client.close()
