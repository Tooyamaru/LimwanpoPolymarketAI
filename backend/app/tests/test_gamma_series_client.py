"""
Gamma Series client tests — Sprint 7.

Uses unittest.mock to intercept httpx calls so no real network is needed.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.gamma_series_client import (
    GammaSeriesClient,
    _parse_dt,
    _extract_tokens,
    GammaToken,
)


# ── _parse_dt helper ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_parse_dt_iso_with_z():
    dt = _parse_dt("2025-01-15T12:00:00Z")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


@pytest.mark.anyio
async def test_parse_dt_iso_with_offset():
    dt = _parse_dt("2025-01-15T12:00:00+00:00")
    assert isinstance(dt, datetime)


@pytest.mark.anyio
async def test_parse_dt_none_input():
    assert _parse_dt(None) is None


@pytest.mark.anyio
async def test_parse_dt_empty_string():
    assert _parse_dt("") is None


@pytest.mark.anyio
async def test_parse_dt_invalid_string():
    assert _parse_dt("not-a-date") is None


# ── _extract_tokens helper ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_extract_tokens_yes_and_no():
    tokens = [
        GammaToken(token_id="yes-123", outcome="Yes"),
        GammaToken(token_id="no-456", outcome="No"),
    ]
    yes_id, no_id = _extract_tokens(tokens)
    assert yes_id == "yes-123"
    assert no_id == "no-456"


@pytest.mark.anyio
async def test_extract_tokens_empty():
    yes_id, no_id = _extract_tokens([])
    assert yes_id is None
    assert no_id is None


@pytest.mark.anyio
async def test_extract_tokens_case_insensitive():
    tokens = [
        GammaToken(token_id="y-tok", outcome="YES"),
        GammaToken(token_id="n-tok", outcome="NO"),
    ]
    yes_id, no_id = _extract_tokens(tokens)
    assert yes_id == "y-tok"
    assert no_id == "n-tok"


# ── shared mock builder ────────────────────────────────────────────────────────

def _make_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _mock_http(return_value=None, side_effect=None):
    """Build a MagicMock that behaves like an httpx.AsyncClient."""
    m = MagicMock()
    m.is_closed = False
    m.aclose = AsyncMock()
    if side_effect is not None:
        m.get = AsyncMock(side_effect=side_effect)
    else:
        m.get = AsyncMock(return_value=return_value)
    return m


# ── GammaSeriesClient.fetch_series ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_series_returns_series():
    client = GammaSeriesClient()
    response = _make_response([{"id": "42", "slug": "btc-up-or-down-5m", "title": "BTC 5m Series"}])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("btc-up-or-down-5m")
    assert series is not None
    assert series.series_id == "42"
    assert series.slug == "btc-up-or-down-5m"
    await client.close()


@pytest.mark.anyio
async def test_fetch_series_returns_none_on_empty():
    client = GammaSeriesClient()
    response = _make_response([])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("unknown-slug")
    assert series is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_series_title_is_set():
    client = GammaSeriesClient()
    response = _make_response([{"id": "99", "slug": "eth-up-or-down-5m", "title": "ETH 5m Series"}])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("eth-up-or-down-5m")
    assert series is not None
    assert series.title == "ETH 5m Series"
    await client.close()


# ── GammaSeriesClient.fetch_events ─────────────────────────────────────────────

def _event_payload():
    return [
        {
            "id": "evt-1",
            "slug": "btc-5m-2025-01-01",
            "title": "Will BTC go up in 5m?",
            "startDate": "2025-01-01T00:00:00Z",
            "endDate": "2025-01-01T00:05:00Z",
            "active": True,
            "closed": False,
            "markets": [
                {
                    "conditionId": "cid-abc",
                    "question": "Will BTC go up in 5m?",
                    "startDate": "2025-01-01T00:00:00Z",
                    "endDate": "2025-01-01T00:05:00Z",
                    "active": True,
                    "closed": False,
                    "tokens": [
                        {"token_id": "yes-tok", "outcome": "Yes"},
                        {"token_id": "no-tok", "outcome": "No"},
                    ],
                }
            ],
        }
    ]


@pytest.mark.anyio
async def test_fetch_events_returns_events():
    client = GammaSeriesClient()
    response = _make_response(_event_payload())
    client._client = _mock_http(return_value=response)

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 1
    event = events[0]
    assert event.event_id == "evt-1"
    assert len(event.markets) == 1
    assert event.markets[0].condition_id == "cid-abc"
    assert event.markets[0].yes_token_id == "yes-tok"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_parses_no_token():
    client = GammaSeriesClient()
    response = _make_response(_event_payload())
    client._client = _mock_http(return_value=response)

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events[0].markets[0].no_token_id == "no-tok"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_skips_events_without_markets():
    payload = [
        {
            "id": "evt-empty",
            "slug": "empty-event",
            "title": "Empty event",
            "startDate": "2025-01-01T00:00:00Z",
            "endDate": "2025-01-01T01:00:00Z",
            "active": True,
            "closed": False,
            "markets": [],
        }
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 0
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_empty_response():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([]))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events == []
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_parses_active_flag():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(_event_payload()))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events[0].is_active is True
    assert events[0].is_closed is False
    await client.close()


# ── GammaSeriesClient.fetch_active_market ──────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_active_market_returns_market():
    now = datetime.now(timezone.utc)
    future_str = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = [
        {
            "id": "evt-active",
            "slug": "active-event",
            "title": "Active event",
            "startDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDate": future_str,
            "active": True,
            "closed": False,
            "markets": [
                {
                    "conditionId": "cid-active",
                    "question": "Will BTC go up?",
                    "startDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "endDate": future_str,
                    "active": True,
                    "closed": False,
                    "tokens": [
                        {"token_id": "yes-t", "outcome": "Yes"},
                        {"token_id": "no-t", "outcome": "No"},
                    ],
                }
            ],
        }
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is not None
    assert market.condition_id == "cid-active"
    await client.close()


@pytest.mark.anyio
async def test_fetch_active_market_returns_none_when_none_active():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([]))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is None
    await client.close()


# ── context manager ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_client_context_manager():
    async with GammaSeriesClient() as client:
        assert client is not None
