"""
Health endpoint tests — Sprint 2.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["version"] == "0.9.0"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], float)


@pytest.mark.anyio
async def test_health_detailed_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/detailed")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_detailed_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/detailed")
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "uptime_seconds" in data
    assert "database" in data
    assert "redis" in data
    assert "engines" in data
    assert isinstance(data["engines"], dict)


@pytest.mark.anyio
async def test_health_detailed_engine_entries_have_correct_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/detailed")
    data = response.json()
    for name, entry in data["engines"].items():
        assert isinstance(name, str)
        assert "status" in entry
        assert entry["status"] in ("alive", "stalled", "not_started")
        # seconds_since_last_cycle is a float when the engine has cycled
        if entry["seconds_since_last_cycle"] is not None:
            assert isinstance(entry["seconds_since_last_cycle"], (int, float))


@pytest.mark.anyio
async def test_health_detailed_not_started_engines_are_visible(client: AsyncClient) -> None:
    """Engines registered but not yet cycled must appear with status='not_started'."""
    response = await client.get("/api/v1/health/detailed")
    data = response.json()
    engines = data["engines"]
    # If any engines are registered, they must all be present in the response
    # (the registered list drives iteration, not just the heartbeats dict)
    from app.core import engine_health as eh
    for name in eh.get_registered():
        assert name in engines, f"registered engine '{name}' missing from /health/detailed"
        assert engines[name]["status"] in ("alive", "stalled", "not_started")
