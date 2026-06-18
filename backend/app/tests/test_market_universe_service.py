"""
Market Universe Service tests — Sprint 7.

Tests the sync logic, status determination, and error-tolerance
of MarketUniverseService using mocked clients.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.market_universe_service import (
    MarketUniverseService,
    SERIES_CATALOG,
    _determine_status,
)
from app.services.gamma_series_client import GammaMarket, GammaEvent, GammaSeries


def _now():
    return datetime.now(timezone.utc)


def _future(s=3600):
    return _now() + timedelta(seconds=s)


def _past(s=3600):
    return _now() - timedelta(seconds=s)


def _make_market(
    condition_id="cid-1",
    is_active=True,
    is_closed=False,
    start_time=None,
    end_time=None,
):
    return GammaMarket(
        condition_id=condition_id,
        question="Will BTC go up?",
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        start_time=start_time or _now(),
        end_time=end_time or _future(),
        is_active=is_active,
        is_closed=is_closed,
    )


def _make_event(markets=None, is_active=True, is_closed=False):
    return GammaEvent(
        event_id="evt-1",
        slug="btc-5m-event",
        title="BTC 5m event",
        start_time=_now(),
        end_time=_future(),
        is_active=is_active,
        is_closed=is_closed,
        markets=markets or [_make_market()],
    )


# ── _determine_status ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_determine_status_closed_is_expired():
    assert _determine_status(True, True, _now(), _future()) == "expired"


@pytest.mark.anyio
async def test_determine_status_past_end_time_is_expired():
    assert _determine_status(False, False, _past(), _past(60)) == "expired"


@pytest.mark.anyio
async def test_determine_status_active_flag_is_active():
    assert _determine_status(True, False, _now(), _future()) == "active"


@pytest.mark.anyio
async def test_determine_status_future_start_time_is_upcoming():
    assert _determine_status(False, False, _future(), _future(7200)) == "upcoming"


@pytest.mark.anyio
async def test_determine_status_no_flags_defaults_upcoming():
    assert _determine_status(False, False, None, None) == "upcoming"


# ── SERIES_CATALOG ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_series_catalog_has_12_entries():
    assert len(SERIES_CATALOG) == 12


@pytest.mark.anyio
async def test_series_catalog_has_all_assets():
    assets = {entry["asset"] for entry in SERIES_CATALOG}
    assert assets == {"BTC", "ETH", "SOL", "XRP"}


@pytest.mark.anyio
async def test_series_catalog_has_all_timeframes():
    timeframes = {entry["timeframe"] for entry in SERIES_CATALOG}
    assert timeframes == {"5m", "15m", "1H"}


@pytest.mark.anyio
async def test_series_catalog_all_have_slugs():
    for entry in SERIES_CATALOG:
        assert entry["slug"], f"Missing slug in {entry}"


@pytest.mark.anyio
async def test_series_catalog_slugs_are_unique():
    slugs = [entry["slug"] for entry in SERIES_CATALOG]
    assert len(slugs) == len(set(slugs))


# ── MarketUniverseService.sync ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_sync_returns_summary_dict():
    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=GammaSeries(series_id="1", slug="test", title="Test"))
    mock_client.fetch_events = AsyncMock(return_value=[])
    mock_client.close = AsyncMock()
    svc._client = mock_client

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market", new=AsyncMock()):
            with patch("app.services.market_universe_service.expire_stale_markets", new=AsyncMock(return_value=0)):
                result = await svc.sync()

    assert "synced_at" in result
    assert "duration_ms" in result
    assert "series_processed" in result
    assert "markets_upserted" in result
    assert "errors" in result
    await svc.close()


@pytest.mark.anyio
async def test_sync_processes_all_12_series():
    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=[])
    mock_client.close = AsyncMock()
    svc._client = mock_client

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market", new=AsyncMock()):
            with patch("app.services.market_universe_service.expire_stale_markets", new=AsyncMock(return_value=0)):
                result = await svc.sync()

    assert result["series_processed"] == 12
    await svc.close()


@pytest.mark.anyio
async def test_sync_last_sync_is_set_after_run():
    svc = MarketUniverseService()
    assert svc.last_sync is None

    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=[])
    mock_client.close = AsyncMock()
    svc._client = mock_client

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market", new=AsyncMock()):
            with patch("app.services.market_universe_service.expire_stale_markets", new=AsyncMock(return_value=0)):
                await svc.sync()

    assert svc.last_sync is not None
    assert svc.last_sync_duration_ms is not None
    await svc.close()


@pytest.mark.anyio
async def test_sync_errors_are_collected_not_raised():
    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(side_effect=RuntimeError("network failure"))
    mock_client.fetch_events = AsyncMock(side_effect=RuntimeError("network failure"))
    mock_client.close = AsyncMock()
    svc._client = mock_client

    with patch("app.services.market_universe_service.get_session_factory"):
        with patch("app.services.market_universe_service.upsert_universe_market", new=AsyncMock()):
            with patch("app.services.market_universe_service.expire_stale_markets", new=AsyncMock(return_value=0)):
                result = await svc.sync()

    assert len(result["errors"]) > 0
    await svc.close()
