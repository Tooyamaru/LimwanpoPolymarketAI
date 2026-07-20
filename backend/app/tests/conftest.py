"""
Pytest configuration and shared fixtures.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def init_test_database():
    """
    Create all DB tables once per test session before any test runs.

    The test client uses ASGITransport which bypasses the FastAPI lifespan
    (and therefore skips the app startup init_db() call). Without this
    fixture the portfolio_api integration tests fail with:
        UndefinedTableError: relation "positions" does not exist
    """
    from app.core.database import init_db
    await init_db()


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """
    Reset the SQLAlchemy async engine singleton before AND after each test.

    asyncpg connections are bound to the event loop that created them.
    pytest-asyncio creates a fresh loop per test by default.  Without the
    pre-test reset, the engine created during the session-scoped
    init_test_database fixture (which runs on the session's event loop) is
    still alive when the first test starts on its own event loop, causing:
        RuntimeError: Task got Future attached to a different loop

    Resetting before yielding ensures every test starts with a clean engine
    that will connect on the current test's event loop.  Resetting after
    yielding (existing behaviour) cleans up so the next test also starts
    fresh.
    """
    # ── Pre-test reset ────────────────────────────────────────────────────────
    from app.core import database
    if database._engine is not None:
        try:
            await database._engine.dispose()
        except Exception:
            pass
        database._engine = None
        database._session_factory = None

    yield

    # ── Post-test reset ───────────────────────────────────────────────────────
    if database._engine is not None:
        try:
            await database._engine.dispose()
        except Exception:
            pass
        database._engine = None
        database._session_factory = None
