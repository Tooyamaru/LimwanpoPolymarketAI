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
    assert data["version"] == "0.2.0"
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
