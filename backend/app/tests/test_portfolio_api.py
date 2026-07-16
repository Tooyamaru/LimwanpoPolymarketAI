"""
Portfolio API tests — Layer 10: Portfolio Reporting.

Integration tests using HTTPX AsyncClient against the full FastAPI app.
Tests all five read-only /portfolio/* endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── GET /api/v1/portfolio/summary ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_summary_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_portfolio_summary_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/summary")
    data = response.json()
    assert "total_predictions" in data
    assert "active_predictions" in data
    assert "resolved_predictions" in data
    assert "total_orders" in data
    assert "executed_orders" in data
    assert "approved_decisions" in data
    assert "blocked_decisions" in data


@pytest.mark.anyio
async def test_portfolio_summary_types(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/summary")
    data = response.json()
    assert isinstance(data["total_predictions"], int)
    assert isinstance(data["active_predictions"], int)
    assert isinstance(data["total_orders"], int)
    assert isinstance(data["approved_decisions"], int)
    assert isinstance(data["blocked_decisions"], int)


# ── GET /api/v1/portfolio/positions ──────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_positions_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/positions")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_portfolio_positions_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/positions")
    data = response.json()
    assert "total_predictions" in data
    assert "active_predictions" in data
    assert "resolved_predictions" in data
    assert "by_asset" in data
    assert "by_side" in data
    assert isinstance(data["by_asset"], dict)
    assert isinstance(data["by_side"], dict)


# ── GET /api/v1/portfolio/orders ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_orders_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/orders")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_portfolio_orders_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/orders")
    data = response.json()
    assert "total_orders" in data
    assert "filled_orders" in data
    assert "pending_orders" in data
    assert "by_asset" in data
    assert "by_side" in data
    assert isinstance(data["by_asset"], dict)
    assert isinstance(data["by_side"], dict)


# ── GET /api/v1/portfolio/risk ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_risk_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/risk")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_portfolio_risk_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/risk")
    data = response.json()
    assert "total_checked" in data
    assert "allowed" in data
    assert "blocked" in data
    assert "block_rate_pct" in data
    assert "by_reason" in data
    assert isinstance(data["by_reason"], dict)
    assert isinstance(data["block_rate_pct"], float)


# ── GET /api/v1/portfolio/pnl ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_pnl_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/pnl")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_portfolio_pnl_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/pnl")
    data = response.json()
    assert "active_predictions" in data
    assert "total_live_state" in data
    assert "average_live_state" in data
    assert "resolved_predictions" in data
    assert "total_resolution_result" in data


@pytest.mark.anyio
async def test_portfolio_pnl_types(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/pnl")
    data = response.json()
    assert isinstance(data["active_predictions"], int)
    assert isinstance(data["total_live_state"], float)
    assert isinstance(data["average_live_state"], float)
    assert isinstance(data["resolved_predictions"], int)
    assert isinstance(data["total_resolution_result"], float)


# ── Non-existent endpoints return 404 ────────────────────────────────────────

@pytest.mark.anyio
async def test_portfolio_unknown_path_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/unknown")
    assert response.status_code == 404
