"""
Gamma Series client tests — Sprint 7 / Sprint 8.6 fix.

Uses unittest.mock to intercept httpx calls so no real network is needed.

Sprint 8.6 changes:
  - fetch_events uses GET /events?series_slug=&order=startDate&ascending=false
    (flat event list with markets embedded) instead of GET /series (events
    with empty markets[]).
  - fetch_events internally filters expired/closed events and sorts by
    end_time ascending, so index 0 is always the active market.
  - fetch_active_market and fetch_next_markets rely on that sort order.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.gamma_series_client import (
    GammaSeriesClient,
    _parse_dt,
    _extract_clob_token_ids,
)


# ── _parse_dt helper ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_parse_dt_iso_with_z():
    dt = _parse_dt("2025-01-15T12:00:00Z")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


@pytest.mark.anyio
async def test_parse_dt_iso_with_offset():
    dt = _parse_dt("2025-01-15T12:00:00+00:00")
    assert isinstance(dt, datetime)


@pytest.mark.anyio
async def test_parse_dt_none_input():
    assert _parse_dt(None) is None


@pytest.mark.anyio
async def test_parse_dt_empty_string():
    assert _parse_dt("") is None


@pytest.mark.anyio
async def test_parse_dt_invalid_string():
    assert _parse_dt("not-a-date") is None


# ── _extract_clob_token_ids helper ────────────────────────────────────────────

@pytest.mark.anyio
async def test_extract_clob_token_ids_valid():
    raw = json.dumps(["yes-token-111", "no-token-222"])
    yes_id, no_id = _extract_clob_token_ids(raw)
    assert yes_id == "yes-token-111"
    assert no_id == "no-token-222"


@pytest.mark.anyio
async def test_extract_clob_token_ids_none_input():
    yes_id, no_id = _extract_clob_token_ids(None)
    assert yes_id is None
    assert no_id is None


@pytest.mark.anyio
async def test_extract_clob_token_ids_empty_string():
    yes_id, no_id = _extract_clob_token_ids("")
    assert yes_id is None
    assert no_id is None


@pytest.mark.anyio
async def test_extract_clob_token_ids_malformed_json():
    yes_id, no_id = _extract_clob_token_ids("not-json")
    assert yes_id is None
    assert no_id is None


@pytest.mark.anyio
async def test_extract_clob_token_ids_single_entry():
    raw = json.dumps(["only-one"])
    yes_id, no_id = _extract_clob_token_ids(raw)
    assert yes_id == "only-one"
    assert no_id is None


@pytest.mark.anyio
async def test_extract_clob_token_ids_numeric_token_ids():
    raw = json.dumps(["89914745434197090", "54523562982062900"])
    yes_id, no_id = _extract_clob_token_ids(raw)
    assert yes_id == "89914745434197090"
    assert no_id == "54523562982062900"


@pytest.mark.anyio
async def test_extract_clob_token_ids_first_is_yes():
    raw = json.dumps(["YES-TOKEN", "NO-TOKEN", "extra"])
    yes_id, no_id = _extract_clob_token_ids(raw)
    assert yes_id == "YES-TOKEN"
    assert no_id == "NO-TOKEN"


# ── shared mock builder ────────────────────────────────────────────────────────

def _make_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _mock_http(return_value=None, side_effect=None):
    """Build a MagicMock that behaves like an httpx.AsyncClient."""
    m = MagicMock()
    m.is_closed = False
    m.aclose = AsyncMock()
    if side_effect is not None:
        m.get = AsyncMock(side_effect=side_effect)
    else:
        m.get = AsyncMock(return_value=return_value)
    return m


# ── Event payload helpers (flat list, as returned by GET /events) ──────────────

def _make_market_dict(
    condition_id="cid-abc",
    question="Will BTC go up?",
    end_offset_h=1,
    active=True,
    closed=False,
    yes_token="yes-tok",
    no_token="no-tok",
):
    """Build a raw market dict using the clobTokenIds field."""
    now = datetime.now(timezone.utc)
    return {
        "conditionId": condition_id,
        "question": question,
        "startDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDate": (now + timedelta(hours=end_offset_h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "active": active,
        "closed": closed,
        "clobTokenIds": json.dumps([yes_token, no_token]),
    }


def _make_event_dict(
    event_id="evt-1",
    slug="btc-5m-event",
    title="BTC 5m event",
    end_offset_h=1,
    active=True,
    closed=False,
    markets=None,
):
    """Build a raw event dict as returned directly by GET /events."""
    now = datetime.now(timezone.utc)
    return {
        "id": event_id,
        "slug": slug,
        "title": title,
        "startDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDate": (now + timedelta(hours=end_offset_h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "active": active,
        "closed": closed,
        "markets": markets if markets is not None else [_make_market_dict()],
    }


# ── GammaSeriesClient.fetch_series ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_series_returns_series():
    client = GammaSeriesClient()
    response = _make_response([{"id": "42", "slug": "btc-up-or-down-5m", "title": "BTC 5m Series"}])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("btc-up-or-down-5m")
    assert series is not None
    assert series.series_id == "42"
    assert series.slug == "btc-up-or-down-5m"
    await client.close()


@pytest.mark.anyio
async def test_fetch_series_returns_none_on_empty():
    client = GammaSeriesClient()
    response = _make_response([])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("unknown-slug")
    assert series is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_series_title_is_set():
    client = GammaSeriesClient()
    response = _make_response([{"id": "99", "slug": "eth-up-or-down-5m", "title": "ETH 5m Series"}])
    client._client = _mock_http(return_value=response)

    series = await client.fetch_series("eth-up-or-down-5m")
    assert series is not None
    assert series.title == "ETH 5m Series"
    await client.close()


# ── GammaSeriesClient.fetch_events (flat events endpoint format) ───────────────

@pytest.mark.anyio
async def test_fetch_events_returns_events():
    client = GammaSeriesClient()
    response = _make_response([_make_event_dict()])
    client._client = _mock_http(return_value=response)

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 1
    event = events[0]
    assert event.event_id == "evt-1"
    assert len(event.markets) == 1
    assert event.markets[0].condition_id == "cid-abc"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_parses_yes_token_from_clob_token_ids():
    client = GammaSeriesClient()
    response = _make_response([_make_event_dict()])
    client._client = _mock_http(return_value=response)

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events[0].markets[0].yes_token_id == "yes-tok"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_parses_no_token_from_clob_token_ids():
    client = GammaSeriesClient()
    response = _make_response([_make_event_dict()])
    client._client = _mock_http(return_value=response)

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events[0].markets[0].no_token_id == "no-tok"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_skips_events_without_markets():
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_event_dict(markets=[])])
    )

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 0
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_empty_response():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([]))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events == []
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_parses_active_flag():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([_make_event_dict()]))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert events[0].is_active is True
    assert events[0].is_closed is False
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_multiple_events_parsed():
    payload = [_make_event_dict(event_id=f"evt-{i}", end_offset_h=i + 1) for i in range(3)]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 3
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_sorted_by_end_time_ascending():
    """fetch_events must return events sorted by end_time ascending (active first)."""
    payload = [
        _make_event_dict(event_id="evt-far",  end_offset_h=5,
                         markets=[_make_market_dict(condition_id="cid-far",  end_offset_h=5)]),
        _make_event_dict(event_id="evt-near", end_offset_h=1,
                         markets=[_make_market_dict(condition_id="cid-near", end_offset_h=1)]),
        _make_event_dict(event_id="evt-mid",  end_offset_h=3,
                         markets=[_make_market_dict(condition_id="cid-mid",  end_offset_h=3)]),
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 3
    assert events[0].markets[0].condition_id == "cid-near"
    assert events[1].markets[0].condition_id == "cid-mid"
    assert events[2].markets[0].condition_id == "cid-far"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_filters_closed_events():
    """fetch_events must exclude closed events."""
    payload = [
        _make_event_dict(event_id="evt-closed", closed=True,
                         markets=[_make_market_dict(condition_id="cid-closed")]),
        _make_event_dict(event_id="evt-open",   closed=False,
                         markets=[_make_market_dict(condition_id="cid-open")]),
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    events = await client.fetch_events("btc-up-or-down-5m")
    assert len(events) == 1
    assert events[0].event_id == "evt-open"
    await client.close()


@pytest.mark.anyio
async def test_fetch_events_real_clob_token_ids_format():
    """Test with the actual long numeric token IDs from the live API."""
    yes_tok = "89914745434197090561768660642928718885215370230365649728388341572530801712855"
    no_tok = "54523562982062900990767835060308686008217934365568088060293219956372385944551"
    market_dict = _make_market_dict(
        condition_id="0x81326c52f1df0c6ae70b553dc84b3ef6ae7b5769dd086a4046aa864d71545d15",
        yes_token=yes_tok,
        no_token=no_tok,
    )
    payload = [_make_event_dict(markets=[market_dict])]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    events = await client.fetch_events("btc-up-or-down-5m")
    m = events[0].markets[0]
    assert m.yes_token_id == yes_tok
    assert m.no_token_id == no_tok
    assert m.condition_id == "0x81326c52f1df0c6ae70b553dc84b3ef6ae7b5769dd086a4046aa864d71545d15"
    await client.close()


# ── GammaSeriesClient.fetch_active_market ──────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_active_market_returns_market():
    payload = [_make_event_dict(event_id="evt-active", end_offset_h=1)]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is not None
    assert market.condition_id == "cid-abc"
    await client.close()


@pytest.mark.anyio
async def test_fetch_active_market_returns_none_when_none_active():
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([]))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_active_market_returns_soonest_expiring():
    """Active market must be the one with the earliest future end_time."""
    payload = [
        _make_event_dict(event_id="evt-far",  end_offset_h=5,
                         markets=[_make_market_dict(condition_id="cid-far",  end_offset_h=5)]),
        _make_event_dict(event_id="evt-near", end_offset_h=1,
                         markets=[_make_market_dict(condition_id="cid-near", end_offset_h=1)]),
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is not None
    assert market.condition_id == "cid-near"
    await client.close()


@pytest.mark.anyio
async def test_fetch_active_market_skips_closed_events():
    payload = [
        _make_event_dict(event_id="evt-closed", closed=True, end_offset_h=1,
                         markets=[_make_market_dict(condition_id="cid-closed", end_offset_h=1)]),
        _make_event_dict(event_id="evt-open",   closed=False, end_offset_h=2,
                         markets=[_make_market_dict(condition_id="cid-open",   end_offset_h=2)]),
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    market = await client.fetch_active_market("btc-up-or-down-5m")
    assert market is not None
    assert market.condition_id == "cid-open"
    await client.close()


# ── GammaSeriesClient.fetch_next_markets ───────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_next_markets_returns_upcoming_after_active():
    """Next markets = all events after index 0 (active)."""
    payload = [
        _make_event_dict(event_id="evt-1", end_offset_h=1,
                         markets=[_make_market_dict(condition_id="cid-1", end_offset_h=1)]),
        _make_event_dict(event_id="evt-2", end_offset_h=2,
                         markets=[_make_market_dict(condition_id="cid-2", end_offset_h=2)]),
        _make_event_dict(event_id="evt-3", end_offset_h=3,
                         markets=[_make_market_dict(condition_id="cid-3", end_offset_h=3)]),
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    markets = await client.fetch_next_markets("btc-up-or-down-5m", count=3)
    assert len(markets) == 2
    cids = [m.condition_id for m in markets]
    assert "cid-2" in cids
    assert "cid-3" in cids
    assert "cid-1" not in cids
    await client.close()


@pytest.mark.anyio
async def test_fetch_next_markets_respects_count_limit():
    payload = [
        _make_event_dict(event_id=f"evt-{i}", end_offset_h=i + 1,
                         markets=[_make_market_dict(condition_id=f"cid-{i}", end_offset_h=i + 1)])
        for i in range(5)
    ]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    markets = await client.fetch_next_markets("btc-up-or-down-5m", count=2)
    assert len(markets) == 2
    await client.close()


@pytest.mark.anyio
async def test_fetch_next_markets_empty_when_only_one_event():
    payload = [_make_event_dict(end_offset_h=1)]
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response(payload))

    markets = await client.fetch_next_markets("btc-up-or-down-5m", count=3)
    assert markets == []
    await client.close()


# ── context manager ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_client_context_manager():
    async with GammaSeriesClient() as client:
        assert client is not None


# ── Phase 9D: _parse_outcome_prices helper ────────────────────────────────────

@pytest.mark.anyio
async def test_parse_outcome_prices_yes_wins():
    """["1", "0"] → YES price=1.0, NO price=0.0"""
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices('["1", "0"]')
    assert yes_p == 1.0
    assert no_p == 0.0


@pytest.mark.anyio
async def test_parse_outcome_prices_no_wins():
    """["0", "1"] → YES price=0.0, NO price=1.0"""
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices('["0", "1"]')
    assert yes_p == 0.0
    assert no_p == 1.0


@pytest.mark.anyio
async def test_parse_outcome_prices_live_probability():
    """["0.505", "0.495"] → live probabilities, not resolution"""
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices('["0.505", "0.495"]')
    assert yes_p == pytest.approx(0.505)
    assert no_p == pytest.approx(0.495)


@pytest.mark.anyio
async def test_parse_outcome_prices_voided():
    """["0", "0"] → both zero (voided/cancelled)"""
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices('["0", "0"]')
    assert yes_p == 0.0
    assert no_p == 0.0


@pytest.mark.anyio
async def test_parse_outcome_prices_none():
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices(None)
    assert yes_p is None
    assert no_p is None


@pytest.mark.anyio
async def test_parse_outcome_prices_empty():
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices("")
    assert yes_p is None
    assert no_p is None


@pytest.mark.anyio
async def test_parse_outcome_prices_malformed():
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices("not-json")
    assert yes_p is None
    assert no_p is None


@pytest.mark.anyio
async def test_parse_outcome_prices_single_entry():
    yes_p, no_p = GammaSeriesClient._parse_outcome_prices('["1"]')
    assert yes_p == 1.0
    assert no_p is None


# ── Phase 9D: fetch_market_resolution ─────────────────────────────────────────

def _make_market_resolution_dict(
    condition_id="cid-abc",
    closed=True,
    active=False,
    outcome_prices='["1", "0"]',
    clob_token_ids=None,
):
    """Build a raw market dict as returned by GET /markets?condition_ids=."""
    if clob_token_ids is None:
        clob_token_ids = json.dumps(["yes-token-111", "no-token-222"])
    return {
        "conditionId": condition_id,
        "question": "Will BTC go up?",
        "closed": closed,
        "active": active,
        "outcomePrices": outcome_prices,
        "clobTokenIds": clob_token_ids,
        "startDate": "2026-07-10T00:00:00Z",
        "endDate": "2026-07-10T01:00:00Z",
    }


@pytest.mark.anyio
async def test_fetch_market_resolution_yes_wins():
    """Closed market with outcomePrices=["1","0"] → YES wins, DIRECT_POLYMARKET_RESOLUTION."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_DIRECT
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=True,
            outcome_prices='["1", "0"]',
        )])
    )
    result = await client.fetch_market_resolution(
        "cid-abc", yes_token_id="yes-token-111", no_token_id="no-token-222"
    )
    assert result.outcome_source == OUTCOME_SOURCE_DIRECT
    assert result.winning_side == "YES"
    assert result.winning_token_id == "yes-token-111"
    assert result.final_yes_price == pytest.approx(1.0)
    assert result.final_no_price == pytest.approx(0.0)
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_no_wins():
    """Closed market with outcomePrices=["0","1"] → NO wins, DIRECT_POLYMARKET_RESOLUTION."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_DIRECT
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=True,
            outcome_prices='["0", "1"]',
        )])
    )
    result = await client.fetch_market_resolution(
        "cid-abc", yes_token_id="yes-token-111", no_token_id="no-token-222"
    )
    assert result.outcome_source == OUTCOME_SOURCE_DIRECT
    assert result.winning_side == "NO"
    assert result.winning_token_id == "no-token-222"
    assert result.final_yes_price == pytest.approx(0.0)
    assert result.final_no_price == pytest.approx(1.0)
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_live_probability_not_resolved():
    """Live market with outcomePrices=[0.51, 0.49] is NOT a resolution."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=False,
            active=True,
            outcome_prices='["0.51", "0.49"]',
        )])
    )
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_voided_market():
    """Closed market with outcomePrices=["0","0"] → voided, NOT_AVAILABLE."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=True,
            outcome_prices='["0", "0"]',
        )])
    )
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_empty_response():
    """Empty API response → NOT_AVAILABLE."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([]))
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_condition_id_mismatch():
    """API returns a market with a different condition_id → NOT_AVAILABLE."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-OTHER",  # different from what we're looking for
            closed=True,
            outcome_prices='["1", "0"]',
        )])
    )
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_missing_outcome_prices():
    """Closed market with no outcomePrices → NOT_AVAILABLE."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    market = _make_market_resolution_dict(
        condition_id="cid-abc",
        closed=True,
        outcome_prices=None,
    )
    del market["outcomePrices"]  # remove entirely
    client = GammaSeriesClient()
    client._client = _mock_http(return_value=_make_response([market]))
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_ambiguous_prices():
    """Closed market with outcomePrices=["0.5","0.5"] → NOT_AVAILABLE (below threshold)."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_NONE
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=True,
            outcome_prices='["0.5", "0.5"]',
        )])
    )
    result = await client.fetch_market_resolution("cid-abc")
    assert result.outcome_source == OUTCOME_SOURCE_NONE
    assert result.winning_side is None
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_threshold_boundary_yes():
    """outcomePrices=["0.99","0.01"] meets threshold → YES wins."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_DIRECT
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="cid-abc",
            closed=True,
            outcome_prices='["0.99", "0.01"]',
        )])
    )
    result = await client.fetch_market_resolution("cid-abc", yes_token_id="yes-tok")
    assert result.outcome_source == OUTCOME_SOURCE_DIRECT
    assert result.winning_side == "YES"
    await client.close()


@pytest.mark.anyio
async def test_fetch_market_resolution_condition_id_case_insensitive():
    """condition_id match is case-insensitive (hex hashes may differ in case)."""
    from app.services.gamma_series_client import OUTCOME_SOURCE_DIRECT
    client = GammaSeriesClient()
    client._client = _mock_http(
        return_value=_make_response([_make_market_resolution_dict(
            condition_id="0xABCDEF",
            closed=True,
            outcome_prices='["1", "0"]',
        )])
    )
    result = await client.fetch_market_resolution("0xabcdef")
    assert result.outcome_source == OUTCOME_SOURCE_DIRECT
    await client.close()
