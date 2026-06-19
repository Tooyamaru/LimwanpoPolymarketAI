"""
Market Universe Service tests — Sprint 7 / Sprint 8.5 fix.

Tests the sync logic, status determination, and error-tolerance
of MarketUniverseService using mocked clients.

Sprint 8.5 additions:
  - test_sync_marks_first_event_active
  - test_sync_marks_remaining_events_upcoming
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

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


def _make_event(
    markets=None,
    is_active=True,
    is_closed=False,
    end_time=None,
    event_id="evt-1",
):
    return GammaEvent(
        event_id=event_id,
        slug="btc-5m-event",
        title="BTC 5m event",
        start_time=_now(),
        end_time=end_time or _future(),
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


# ── Sprint 8.5: active vs upcoming status assignment ──────────────────────────

@pytest.mark.anyio
async def test_sync_marks_first_event_active():
    """
    When the series returns multiple open events, the one with the
    soonest end_time must be upserted with status="active".
    """
    # Two events: near=1h away, far=5h away — both active=True from API
    near_end = _future(3600)
    far_end = _future(18000)
    events_returned = [
        _make_event(
            event_id="evt-near",
            end_time=near_end,
            markets=[_make_market(condition_id="cid-near", end_time=near_end)],
        ),
        _make_event(
            event_id="evt-far",
            end_time=far_end,
            markets=[_make_market(condition_id="cid-far", end_time=far_end)],
        ),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch(
            "app.services.market_universe_service.upsert_universe_market",
            side_effect=capture_upsert,
        ):
            with patch(
                "app.services.market_universe_service.expire_stale_markets",
                new=AsyncMock(return_value=0),
            ):
                await svc.sync()

    near_calls = [c for c in captured if c.get("condition_id") == "cid-near"]
    assert any(c["status"] == "active" for c in near_calls), \
        "soonest-expiring event must be marked active"
    await svc.close()


@pytest.mark.anyio
async def test_sync_marks_remaining_events_upcoming():
    """
    All events after the first (active) one must be upserted with
    status="upcoming".
    """
    near_end = _future(3600)
    mid_end = _future(7200)
    far_end = _future(10800)
    events_returned = [
        _make_event(
            event_id="evt-near",
            end_time=near_end,
            markets=[_make_market(condition_id="cid-near", end_time=near_end)],
        ),
        _make_event(
            event_id="evt-mid",
            end_time=mid_end,
            markets=[_make_market(condition_id="cid-mid", end_time=mid_end)],
        ),
        _make_event(
            event_id="evt-far",
            end_time=far_end,
            markets=[_make_market(condition_id="cid-far", end_time=far_end)],
        ),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch(
            "app.services.market_universe_service.upsert_universe_market",
            side_effect=capture_upsert,
        ):
            with patch(
                "app.services.market_universe_service.expire_stale_markets",
                new=AsyncMock(return_value=0),
            ):
                await svc.sync()

    mid_calls = [c for c in captured if c.get("condition_id") == "cid-mid"]
    far_calls = [c for c in captured if c.get("condition_id") == "cid-far"]
    assert any(c["status"] == "upcoming" for c in mid_calls), "second event must be upcoming"
    assert any(c["status"] == "upcoming" for c in far_calls), "third event must be upcoming"
    await svc.close()


# ── Sprint 9.1: market-level active/upcoming enforcement ──────────────────────

@pytest.mark.anyio
async def test_sprint91_three_consecutive_5m_windows_only_first_active():
    """
    Case A: given three future 5m markets (03:00, 03:05, 03:10) inside
    separate events for the same series, only the soonest-expiring market
    (03:00) must be marked active; the other two must be upcoming.
    """
    t0 = _future(300)    # 03:00 — soonest
    t1 = _future(600)    # 03:05
    t2 = _future(900)    # 03:10

    events_returned = [
        _make_event(event_id="evt-0", end_time=t0,
                    markets=[_make_market(condition_id="cid-0300", end_time=t0)]),
        _make_event(event_id="evt-1", end_time=t1,
                    markets=[_make_market(condition_id="cid-0305", end_time=t1)]),
        _make_event(event_id="evt-2", end_time=t2,
                    markets=[_make_market(condition_id="cid-0310", end_time=t2)]),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market",
                   side_effect=capture_upsert):
            with patch("app.services.market_universe_service.expire_stale_markets",
                       new=AsyncMock(return_value=0)):
                await svc.sync()

    by_cid = {c["condition_id"]: c["status"] for c in captured}
    assert by_cid.get("cid-0300") == "active",  "03:00 must be active"
    assert by_cid.get("cid-0305") == "upcoming", "03:05 must be upcoming"
    assert by_cid.get("cid-0310") == "upcoming", "03:10 must be upcoming"
    await svc.close()


@pytest.mark.anyio
async def test_sprint91_two_markets_same_event_only_soonest_active():
    """
    Case A (multi-market variant): if a single Gamma event contains two
    markets with different end_times, only the market with the smaller
    end_time must be marked active.  This is the exact bug from the audit:
    both markets were previously marked active because they shared idx==0.
    """
    t0 = _future(300)
    t1 = _future(600)

    single_event = GammaEvent(
        event_id="evt-multi",
        slug="eth-5m",
        title="ETH 5m multi-market event",
        start_time=_now(),
        end_time=t1,
        is_active=True,
        is_closed=False,
        markets=[
            _make_market(condition_id="cid-early", end_time=t0),
            _make_market(condition_id="cid-late",  end_time=t1),
        ],
    )

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=[single_event])
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market",
                   side_effect=capture_upsert):
            with patch("app.services.market_universe_service.expire_stale_markets",
                       new=AsyncMock(return_value=0)):
                await svc.sync()

    by_cid = {c["condition_id"]: c["status"] for c in captured}
    assert by_cid.get("cid-early") == "active",  "earlier end_time must be active"
    assert by_cid.get("cid-late")  == "upcoming", "later end_time must be upcoming"
    active_count = sum(1 for s in by_cid.values() if s == "active")
    assert active_count == 1, f"exactly one active market per series, got {active_count}"
    await svc.close()


@pytest.mark.anyio
async def test_sprint91_single_market_is_active():
    """
    Case B: a series with exactly one open market must mark it active.
    """
    t0 = _future(3600)
    events_returned = [
        _make_event(event_id="evt-only", end_time=t0,
                    markets=[_make_market(condition_id="cid-only", end_time=t0)]),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market",
                   side_effect=capture_upsert):
            with patch("app.services.market_universe_service.expire_stale_markets",
                       new=AsyncMock(return_value=0)):
                await svc.sync()

    by_cid = {c["condition_id"]: c["status"] for c in captured}
    assert by_cid.get("cid-only") == "active", "sole open market must be active"
    await svc.close()


@pytest.mark.anyio
async def test_sprint91_expired_market_is_not_active():
    """
    Case C: a market whose end_time is in the past must not be marked
    active and must not be upserted at all (filtered out before ranking).
    """
    past_end   = _past(60)
    future_end = _future(3600)

    events_returned = [
        _make_event(event_id="evt-past", end_time=past_end,
                    markets=[_make_market(condition_id="cid-past", end_time=past_end)]),
        _make_event(event_id="evt-future", end_time=future_end,
                    markets=[_make_market(condition_id="cid-future", end_time=future_end)]),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market",
                   side_effect=capture_upsert):
            with patch("app.services.market_universe_service.expire_stale_markets",
                       new=AsyncMock(return_value=0)):
                await svc.sync()

    condition_ids = [c["condition_id"] for c in captured]
    statuses = {c["condition_id"]: c["status"] for c in captured}
    assert "cid-past" not in condition_ids, "past-end_time market must be filtered out"
    assert statuses.get("cid-future") == "active", "only future market must be active"
    await svc.close()


@pytest.mark.anyio
async def test_sprint91_max_one_active_per_series():
    """
    Case D: regardless of how many open markets are returned by fetch_events,
    the sync must produce exactly ONE active market per (asset, timeframe)
    series entry.  We isolate a single series by patching SERIES_CATALOG.
    """
    # Six future markets with end_times spread 5 minutes apart
    markets_and_events = [
        _make_event(
            event_id=f"evt-{i}",
            end_time=_future(300 * (i + 1)),
            markets=[_make_market(
                condition_id=f"cid-{i}",
                end_time=_future(300 * (i + 1)),
            )],
        )
        for i in range(6)
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=markets_and_events)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    single_series = [{"slug": "eth-up-or-down-5m", "asset": "ETH", "timeframe": "5m"}]

    with patch("app.services.market_universe_service.SERIES_CATALOG", single_series):
        with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.commit = AsyncMock()
            mock_factory_instance = MagicMock()
            mock_factory_instance.return_value = mock_session
            mock_factory.return_value = mock_factory_instance

            with patch("app.services.market_universe_service.upsert_universe_market",
                       side_effect=capture_upsert):
                with patch("app.services.market_universe_service.expire_stale_markets",
                           new=AsyncMock(return_value=0)):
                    await svc.sync()

    active_calls = [c for c in captured if c["status"] == "active"]
    upcoming_calls = [c for c in captured if c["status"] == "upcoming"]
    assert len(active_calls) == 1, \
        f"exactly one active market per series; got {len(active_calls)}: {[c['condition_id'] for c in active_calls]}"
    assert len(upcoming_calls) == 5, \
        f"remaining 5 markets must be upcoming; got {len(upcoming_calls)}"
    assert active_calls[0]["condition_id"] == "cid-0", \
        "cid-0 has the smallest end_time and must be active"
    await svc.close()


@pytest.mark.anyio
async def test_sprint91_no_active_when_all_markets_expired():
    """
    Case C (all expired): if every market returned by fetch_events has a
    past end_time, no upsert should be called (all filtered out).
    """
    events_returned = [
        _make_event(event_id="evt-expired-1", end_time=_past(120),
                    markets=[_make_market(condition_id="cid-exp-1", end_time=_past(120))]),
        _make_event(event_id="evt-expired-2", end_time=_past(60),
                    markets=[_make_market(condition_id="cid-exp-2", end_time=_past(60))]),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch("app.services.market_universe_service.upsert_universe_market",
                   side_effect=capture_upsert):
            with patch("app.services.market_universe_service.expire_stale_markets",
                       new=AsyncMock(return_value=0)):
                await svc.sync()

    active_calls = [c for c in captured if c["status"] == "active"]
    assert len(active_calls) == 0, \
        "no active markets when all have past end_times"
    await svc.close()


@pytest.mark.anyio
async def test_sync_upserts_only_events_returned_by_fetch_events():
    """
    sync() upserts every event that fetch_events() returns.
    Filtering of closed/past events is the responsibility of fetch_events
    (tested in test_gamma_series_client.py), so the mock returns only
    the already-filtered open event — as the real implementation would.
    """
    open_end = _future(3600)
    events_returned = [
        _make_event(
            event_id="evt-open",
            is_closed=False,
            end_time=open_end,
            markets=[_make_market(condition_id="cid-open", end_time=open_end)],
        ),
    ]

    svc = MarketUniverseService()
    mock_client = MagicMock()
    mock_client.fetch_series = AsyncMock(return_value=None)
    mock_client.fetch_events = AsyncMock(return_value=events_returned)
    mock_client.close = AsyncMock()
    svc._client = mock_client

    captured: list[dict] = []

    async def capture_upsert(_session, **kwargs):
        captured.append(kwargs)

    with patch("app.services.market_universe_service.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_factory_instance = MagicMock()
        mock_factory_instance.return_value = mock_session
        mock_factory.return_value = mock_factory_instance

        with patch(
            "app.services.market_universe_service.upsert_universe_market",
            side_effect=capture_upsert,
        ):
            with patch(
                "app.services.market_universe_service.expire_stale_markets",
                new=AsyncMock(return_value=0),
            ):
                await svc.sync()

    condition_ids = [c.get("condition_id") for c in captured]
    assert "cid-open" in condition_ids
    await svc.close()
