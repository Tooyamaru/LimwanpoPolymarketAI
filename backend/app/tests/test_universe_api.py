"""
Universe API endpoint tests — Sprint 7.

Tests all five /api/v1/universe endpoints using httpx.AsyncClient
against the real FastAPI app with in-memory SQLite.
"""

import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, MagicMock

import app.models
from app.core.database import Base
from app.main import app
from app.services.universe_repository import upsert_universe_market

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _now():
    return datetime.now(timezone.utc)


def _future(s=3600):
    return _now() + timedelta(seconds=s)


def _past(s=3600):
    return _now() - timedelta(seconds=s)


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── GET /api/v1/universe ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_universe_returns_200(client):
    resp = await client.get("/api/v1/universe")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_list_universe_returns_list(client):
    resp = await client.get("/api/v1/universe")
    assert isinstance(resp.json(), list)


# ── GET /api/v1/universe/active ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_active_returns_200(client):
    resp = await client.get("/api/v1/universe/active")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_list_active_returns_list(client):
    resp = await client.get("/api/v1/universe/active")
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_list_active_only_active_status(client):
    resp = await client.get("/api/v1/universe/active")
    data = resp.json()
    for item in data:
        assert item["status"] == "active"


# ── GET /api/v1/universe/upcoming ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_upcoming_returns_200(client):
    resp = await client.get("/api/v1/universe/upcoming")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_list_upcoming_returns_list(client):
    resp = await client.get("/api/v1/universe/upcoming")
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_list_upcoming_only_upcoming_status(client):
    resp = await client.get("/api/v1/universe/upcoming")
    data = resp.json()
    for item in data:
        assert item["status"] == "upcoming"


# ── GET /api/v1/universe/stats ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_stats_returns_200(client):
    resp = await client.get("/api/v1/universe/stats")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_stats_has_required_fields(client):
    resp = await client.get("/api/v1/universe/stats")
    data = resp.json()
    assert "total" in data
    assert "by_status" in data
    assert "by_asset" in data
    assert "by_timeframe" in data


@pytest.mark.anyio
async def test_stats_by_status_has_all_states(client):
    resp = await client.get("/api/v1/universe/stats")
    by_status = resp.json()["by_status"]
    assert "active" in by_status
    assert "upcoming" in by_status
    assert "expired" in by_status


@pytest.mark.anyio
async def test_stats_by_asset_has_all_assets(client):
    resp = await client.get("/api/v1/universe/stats")
    by_asset = resp.json()["by_asset"]
    for asset in ["BTC", "ETH", "SOL", "XRP"]:
        assert asset in by_asset


@pytest.mark.anyio
async def test_stats_by_timeframe_has_all_timeframes(client):
    resp = await client.get("/api/v1/universe/stats")
    by_tf = resp.json()["by_timeframe"]
    for tf in ["5m", "15m", "1H"]:
        assert tf in by_tf


@pytest.mark.anyio
async def test_stats_total_is_integer(client):
    resp = await client.get("/api/v1/universe/stats")
    assert isinstance(resp.json()["total"], int)


# ── POST /api/v1/universe/sync ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_sync_returns_200(client):
    with MagicMock() as mock_svc:
        mock_svc.sync = AsyncMock(return_value={
            "synced_at": "2025-01-01T00:00:00+00:00",
            "duration_ms": 500.0,
            "series_processed": 12,
            "markets_upserted": 36,
            "markets_expired_by_time": 0,
            "errors": [],
        })
        app.state.universe_service = mock_svc
        resp = await client.post("/api/v1/universe/sync")
        del app.state.universe_service

    assert resp.status_code == 200


@pytest.mark.anyio
async def test_sync_response_has_required_fields(client):
    with MagicMock() as mock_svc:
        mock_svc.sync = AsyncMock(return_value={
            "synced_at": "2025-01-01T00:00:00+00:00",
            "duration_ms": 123.4,
            "series_processed": 12,
            "markets_upserted": 24,
            "markets_expired_by_time": 2,
            "errors": [],
        })
        app.state.universe_service = mock_svc
        resp = await client.post("/api/v1/universe/sync")
        del app.state.universe_service

    data = resp.json()
    assert "synced_at" in data
    assert "duration_ms" in data
    assert "series_processed" in data
    assert "markets_upserted" in data
    assert "markets_expired_by_time" in data
    assert "errors" in data


@pytest.mark.anyio
async def test_sync_errors_is_list(client):
    with MagicMock() as mock_svc:
        mock_svc.sync = AsyncMock(return_value={
            "synced_at": "2025-01-01T00:00:00+00:00",
            "duration_ms": 99.0,
            "series_processed": 12,
            "markets_upserted": 0,
            "markets_expired_by_time": 0,
            "errors": [],
        })
        app.state.universe_service = mock_svc
        resp = await client.post("/api/v1/universe/sync")
        del app.state.universe_service

    assert isinstance(resp.json()["errors"], list)
