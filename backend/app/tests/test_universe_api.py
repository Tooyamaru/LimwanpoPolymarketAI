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
from app.repositories.universe_repository import upsert_universe_market

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


# ── event_slug API exposure (handoff spec items 4-5, 20-22) ──────────────────
# NOTE: app, Base, upsert_universe_market are already imported at the top of
# this file.  Do NOT re-import app.models or app.main here — doing so would
# shadow the `app` name (FastAPI instance → module) and break other fixtures.

from datetime import timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.database import get_db_session

_TEST_DB_URL_SLUG = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def slug_db_client():
    """Client backed by an isolated in-memory DB containing one market with event_slug."""
    engine = create_async_engine(_TEST_DB_URL_SLUG, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(timezone.utc)
    slot = int(now.timestamp() // 300) * 300
    pw_start = datetime.fromtimestamp(slot, tz=timezone.utc)
    pw_end   = pw_start + timedelta(seconds=300)
    ev_slug  = f"btc-updown-5m-{slot}"

    async with factory() as session:
        await upsert_universe_market(
            session,
            asset="BTC", timeframe="5m",
            series_slug="btc-up-or-down-5m",
            series_id="s-btc", event_id="e-btc",
            condition_id="slug-api-cid-001",
            yes_token_id="yes-tok", no_token_id="no-tok",
            question="Will BTC go up?",
            start_time=pw_start, end_time=pw_end,
            status="active",
            prediction_window_start=pw_start,
            prediction_window_end=pw_end,
            prediction_window_source="slug",
            event_slug=ev_slug,
        )
        await session.commit()

    async def _db_override():
        async with factory() as s:
            yield s

    # Override the shared DB dependency so the endpoint uses our in-memory DB.
    app.dependency_overrides[get_db_session] = _db_override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, ev_slug, slot

    app.dependency_overrides.pop(get_db_session, None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.anyio
async def test_api_exposes_event_slug(slug_db_client):
    """Item 4: /universe/active returns event_slug field."""
    ac, ev_slug, slot = slug_db_client
    resp = await ac.get("/api/v1/universe/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0, "expected at least one active market"
    assert "event_slug" in data[0]
    assert data[0]["event_slug"] == ev_slug


@pytest.mark.anyio
async def test_api_exposes_market_slot_timestamp(slug_db_client):
    """Item 5: /universe/active returns market_slot_timestamp matching slug suffix."""
    ac, ev_slug, slot = slug_db_client
    resp = await ac.get("/api/v1/universe/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert data[0]["market_slot_timestamp"] == slot


@pytest.mark.anyio
async def test_api_datetime_serialization(slug_db_client):
    """Item 20: prediction_window_start/end are valid ISO strings, not None."""
    ac, ev_slug, slot = slug_db_client
    resp = await ac.get("/api/v1/universe/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    item = data[0]
    assert item.get("prediction_window_start") is not None
    assert item.get("prediction_window_end") is not None
    # Must parse as ISO datetime without raising
    from datetime import datetime as _dt
    _dt.fromisoformat(item["prediction_window_start"].replace("Z", "+00:00"))
    _dt.fromisoformat(item["prediction_window_end"].replace("Z", "+00:00"))


@pytest.mark.anyio
async def test_active_endpoint_uses_window_live_universe(slug_db_client):
    """Item 21: /universe/active selects markets via prediction window, not status alone."""
    ac, ev_slug, slot = slug_db_client
    resp = await ac.get("/api/v1/universe/active")
    data = resp.json()
    # If the window is live, the market must appear; countdown_mode must be ENDS_IN
    assert any(
        item.get("countdown_mode") == "ENDS_IN"
        for item in data
    ), "expected ENDS_IN countdown for a market inside its prediction window"


@pytest.mark.anyio
async def test_api_event_slug_not_null_when_stored(slug_db_client):
    """Item 4 (negative): event_slug must not be silently null when DB has a valid slug."""
    ac, ev_slug, slot = slug_db_client
    resp = await ac.get("/api/v1/universe/active")
    data = resp.json()
    for item in data:
        if item.get("condition_id") == "slug-api-cid-001":
            assert item["event_slug"] is not None
            return
    # If the market wasn't returned, that's a separate failure handled by other tests
