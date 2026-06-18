"""
Pytest configuration and shared fixtures.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """
    Reset the SQLAlchemy async engine singleton after each test function.

    asyncpg connections are bound to the event loop that created them.
    pytest-asyncio creates a fresh loop per test by default, so without
    this reset the engine from test N tries to reuse connections that
    belong to test N-1's (now-closed) loop, causing:
        RuntimeError: Task got Future attached to a different loop
    """
    yield
    from app.core import database
    if database._engine is not None:
        try:
            await database._engine.dispose()
        except Exception:
            pass
        database._engine = None
        database._session_factory = None
