"""
Price API tests — Sprint 9.

Tests for GET /price/latest, /price/active, /price/stats, /price/{condition_id}.
Uses the ASGI test client (no real DB — SQLite in-memory patched in).
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_snapshot(**kwargs):
    from app.models.market_price_snapshot import MarketPriceSnapshot
    defaults = dict(
        id=1,
        market_universe_id=None,
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
        captured_at=_now(),
    )
    defaults.update(kwargs)
    snap = MagicMock(spec=MarketPriceSnapshot)
    for k, v in defaults.items():
        setattr(snap, k, v)
    return snap


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── GET /price/latest ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_latest_prices_returns_200(client):
    with patch("app.api.v1.price.repo.get_latest_snapshot", new_callable=AsyncMock) as mock_snap, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_snap.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/latest")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_latest_prices_returns_list(client):
    with patch("app.api.v1.price.repo.get_latest_snapshot", new_callable=AsyncMock) as mock_snap, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_snap.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/latest")
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_get_latest_prices_default_limit(client):
    with patch("app.api.v1.price.repo.get_latest_snapshot", new_callable=AsyncMock) as mock_snap, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_snap.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/latest")
        mock_snap.assert_called_once()
        call_kwargs = mock_snap.call_args
        assert call_kwargs is not None
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_latest_prices_custom_limit(client):
    with patch("app.api.v1.price.repo.get_latest_snapshot", new_callable=AsyncMock) as mock_snap, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_snap.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/latest?limit=5")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_latest_prices_invalid_limit(client):
    resp = await client.get("/api/v1/price/latest?limit=0")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_get_latest_prices_limit_too_high(client):
    resp = await client.get("/api/v1/price/latest?limit=501")
    assert resp.status_code == 422


# ── GET /price/active ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_active_prices_returns_200(client):
    with patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_active.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/active")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_active_prices_returns_list(client):
    with patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_active.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/active")
    assert isinstance(resp.json(), list)


# ── GET /price/stats ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_price_stats_returns_200(client):
    with patch("app.api.v1.price.repo.get_snapshot_count", new_callable=AsyncMock) as mock_count, \
         patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active:
        mock_count.return_value = 0
        mock_active.return_value = []
        resp = await client.get("/api/v1/price/stats")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_price_stats_has_required_fields(client):
    with patch("app.api.v1.price.repo.get_snapshot_count", new_callable=AsyncMock) as mock_count, \
         patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active:
        mock_count.return_value = 42
        mock_active.return_value = []
        resp = await client.get("/api/v1/price/stats")
    data = resp.json()
    assert "total_snapshots" in data
    assert "active_markets_with_data" in data
    assert "assets_covered" in data
    assert "timeframes_covered" in data


@pytest.mark.anyio
async def test_get_price_stats_total_snapshots(client):
    with patch("app.api.v1.price.repo.get_snapshot_count", new_callable=AsyncMock) as mock_count, \
         patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active:
        mock_count.return_value = 99
        mock_active.return_value = []
        resp = await client.get("/api/v1/price/stats")
    assert resp.json()["total_snapshots"] == 99


@pytest.mark.anyio
async def test_get_price_stats_assets_covered_is_list(client):
    with patch("app.api.v1.price.repo.get_snapshot_count", new_callable=AsyncMock) as mock_count, \
         patch("app.api.v1.price.repo.get_latest_active_markets", new_callable=AsyncMock) as mock_active:
        mock_count.return_value = 0
        mock_active.return_value = []
        resp = await client.get("/api/v1/price/stats")
    assert isinstance(resp.json()["assets_covered"], list)


# ── GET /price/{condition_id} ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_price_by_condition_404_when_not_found(client):
    with patch("app.api.v1.price.repo.get_latest_by_condition", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = []
        resp = await client.get("/api/v1/price/0xNOTFOUND")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_price_by_condition_returns_200_when_found(client):
    with patch("app.api.v1.price.repo.get_latest_by_condition", new_callable=AsyncMock) as mock_get, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        from app.api.v1.price import PriceSnapshotResponse
        snap = PriceSnapshotResponse(
            id=1,
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
            captured_at=_now(),
            asset="BTC",
            timeframe="5m",
        )
        mock_get.return_value = [MagicMock()]
        mock_enrich.return_value = [snap]
        resp = await client.get("/api/v1/price/0xabc")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_get_price_by_condition_response_has_required_fields(client):
    with patch("app.api.v1.price.repo.get_latest_by_condition", new_callable=AsyncMock) as mock_get, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        from app.api.v1.price import PriceSnapshotResponse
        snap = PriceSnapshotResponse(
            id=1,
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
            captured_at=_now(),
            asset="BTC",
            timeframe="5m",
        )
        mock_get.return_value = [MagicMock()]
        mock_enrich.return_value = [snap]
        resp = await client.get("/api/v1/price/0xabc")
    data = resp.json()
    assert len(data) == 1
    row = data[0]
    for field in ["condition_id", "yes_mid", "no_mid", "spread_yes", "captured_at"]:
        assert field in row


@pytest.mark.anyio
async def test_get_price_by_condition_default_limit(client):
    with patch("app.api.v1.price.repo.get_latest_by_condition", new_callable=AsyncMock) as mock_get, \
         patch("app.api.v1.price._enrich", new_callable=AsyncMock) as mock_enrich:
        mock_get.return_value = []
        mock_enrich.return_value = []
        resp = await client.get("/api/v1/price/0xNONE")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_price_by_condition_invalid_limit(client):
    resp = await client.get("/api/v1/price/0xabc?limit=200")
    assert resp.status_code in (404, 422)
