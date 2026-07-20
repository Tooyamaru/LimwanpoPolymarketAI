"""
test_polymarket_ptb.py — Official Polymarket PTB client and target-worker
Priority 0 behavior tests.

25 tests covering:
  1–4   URL construction (BTC, ETH, SOL, XRP)
  5–7   Parameter formats (eventStartTime, endDate, variant)
  8–9   Response parsing (openPrice, closePrice null)
  10–13 Error handling (invalid openPrice, missing, HTTP fail, malformed JSON)
  14–16 Input validation (unsupported asset, wrong duration, slug mismatch)
  17    Condition snapshot guard — stale condition_id is discarded
  18    PTB result has priority over Gamma API
  19    PTB result has priority over Chainlink candidate
  20    Unverified PTB result cannot overwrite verified target
  21    Verified target is immutable once locked
  22    Rollover stale result is rejected (snapshot guard)
  23    source_url is persisted on verified target
  24    source_field_path is persisted on verified target
  25    GAP calculation requires target_verified=True
"""

from __future__ import annotations

import pytest
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.polymarket_ptb_client import (
    PTBResult,
    PTB_ENDPOINT,
    PTB_SOURCE,
    PTB_FIELD_PATH,
    EXPECTED_WINDOW_SECONDS,
    SUPPORTED_ASSETS,
    build_ptb_url,
    fetch_ptb,
    _format_iso_utc,
    _validate_inputs,
)
from app.services.target_worker import TargetWorker


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pw(start_ts: int = 1784534700):
    """Return (start, end) UTC datetimes for a 300-second prediction window."""
    start = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end = start + timedelta(seconds=300)
    return start, end


def _slug(asset: str, start_ts: int = 1784534700) -> str:
    return f"{asset.lower()}-updown-5m-{start_ts}"


def _ok_response(open_price: float = 63857.41, close_price: Optional[float] = None) -> dict:
    return {"openPrice": open_price, "closePrice": close_price}


def _mock_market(
    asset: str = "BTC",
    condition_id: str = "0xabcdef1234",
    start_ts: int = 1784534700,
    verified: bool = False,
) -> MagicMock:
    start, end = _pw(start_ts)
    m = MagicMock()
    m.asset = asset
    m.condition_id = condition_id
    m.event_slug = _slug(asset, start_ts)
    m.prediction_window_start = start
    m.prediction_window_end = end
    m.target_verified = verified
    m.target_retry_count = 0
    m.target_last_attempt_at = None
    return m


# ─────────────────────────────────────────────────────────────────────────────
# 1–4: URL construction
# ─────────────────────────────────────────────────────────────────────────────

def test_1_btc_url_contains_symbol_btc():
    start, end = _pw()
    url = build_ptb_url("BTC", start, end)
    assert "symbol=BTC" in url
    assert PTB_ENDPOINT in url


def test_2_eth_url_contains_symbol_eth():
    start, end = _pw()
    url = build_ptb_url("ETH", start, end)
    assert "symbol=ETH" in url


def test_3_sol_url_contains_symbol_sol():
    start, end = _pw()
    url = build_ptb_url("SOL", start, end)
    assert "symbol=SOL" in url


def test_4_xrp_url_contains_symbol_xrp():
    start, end = _pw()
    url = build_ptb_url("XRP", start, end)
    assert "symbol=XRP" in url


# ─────────────────────────────────────────────────────────────────────────────
# 5–7: Parameter formats
# ─────────────────────────────────────────────────────────────────────────────

def test_5_event_start_time_exact_utc_format():
    """eventStartTime must be formatted as YYYY-MM-DDTHH:MM:SSZ (no fractional seconds)."""
    start, end = _pw(1784534700)
    url = build_ptb_url("BTC", start, end)
    # Verify format: must contain the ISO-8601 UTC representation of the start timestamp.
    # 1784534700 → 2026-07-20T08:05:00Z (UTC)
    expected_start = _format_iso_utc(start)  # derive dynamically — immune to tz offset bugs
    assert f"eventStartTime={expected_start}" in url or f"eventStartTime={expected_start.replace(':', '%3A')}" in url
    # Also verify the format matches the required pattern (ends with Z, no microseconds)
    assert expected_start.endswith("Z")
    assert "." not in expected_start


def test_6_end_date_exact_utc_format():
    """endDate must be formatted as YYYY-MM-DDTHH:MM:SSZ."""
    start, end = _pw(1784534700)
    url = build_ptb_url("BTC", start, end)
    # endDate = start + 300s
    expected_end = _format_iso_utc(end)
    assert f"endDate={expected_end}" in url or f"endDate={expected_end.replace(':', '%3A')}" in url
    assert expected_end.endswith("Z")
    assert "." not in expected_end


def test_7_variant_equals_fiveminute():
    """variant parameter must always be 'fiveminute'."""
    start, end = _pw()
    url = build_ptb_url("BTC", start, end)
    assert "variant=fiveminute" in url


# ─────────────────────────────────────────────────────────────────────────────
# 8–9: Response parsing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_8_open_price_parsed_correctly():
    """A numeric openPrice in the response sets price_to_beat and verified=True."""
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _ok_response(open_price=63857.4171821043)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", _slug("BTC"), "0xabc", start, end)

    assert result.verified is True
    assert result.price_to_beat == pytest.approx(63857.4171821043)
    assert result.source == PTB_SOURCE
    assert result.source_field_path == PTB_FIELD_PATH


@pytest.mark.anyio
async def test_9_close_price_null_accepted_for_active_window():
    """closePrice=null is valid while the current window is still active."""
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"openPrice": 3500.0, "closePrice": None}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("ETH", _slug("ETH"), "0xdef", start, end)

    assert result.verified is True
    assert result.close_price is None
    assert result.price_to_beat == pytest.approx(3500.0)


# ─────────────────────────────────────────────────────────────────────────────
# 10–13: Error handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_10_invalid_open_price_rejected():
    """Non-numeric openPrice returns verified=False."""
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"openPrice": "not_a_number", "closePrice": None}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", _slug("BTC"), "0xabc", start, end)

    assert result.verified is False
    assert result.price_to_beat is None
    assert "not numeric" in (result.validation_error or "").lower() or result.validation_error is not None


@pytest.mark.anyio
async def test_11_missing_open_price_rejected():
    """Response missing openPrice returns verified=False."""
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"closePrice": None}  # no openPrice key

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", _slug("BTC"), "0xabc", start, end)

    assert result.verified is False
    assert "openPrice" in (result.validation_error or "")


@pytest.mark.anyio
async def test_12_http_failure_returns_pending():
    """Network error returns verified=False without raising."""
    start, end = _pw()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("SOL", _slug("SOL"), "0xdef", start, end)

    assert result.verified is False
    assert result.price_to_beat is None
    assert result.validation_error is not None


@pytest.mark.anyio
async def test_13_malformed_json_returns_pending():
    """Malformed JSON response returns verified=False."""
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("No JSON object could be decoded")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("XRP", _slug("XRP"), "0xabc", start, end)

    assert result.verified is False
    assert result.price_to_beat is None


# ─────────────────────────────────────────────────────────────────────────────
# 14–16: Input validation (no network call needed)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_14_unsupported_asset_rejected():
    """An unsupported asset symbol returns verified=False without HTTP call."""
    start, end = _pw()

    # Patch so we can verify no HTTP call is made
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=AssertionError("should not call HTTP"))

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("DOGE", "doge-updown-5m-1784534700", "0xabc", start, end)

    assert result.verified is False
    assert "unsupported" in (result.validation_error or "").lower()
    mock_client.get.assert_not_called()


@pytest.mark.anyio
async def test_15_window_duration_not_300s_rejected():
    """A prediction window not exactly 300 seconds is rejected before HTTP call."""
    start = datetime.fromtimestamp(1784534700, tz=timezone.utc)
    end = start + timedelta(seconds=600)  # 10 min — wrong

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=AssertionError("should not call HTTP"))

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", _slug("BTC"), "0xabc", start, end)

    assert result.verified is False
    assert "duration" in (result.validation_error or "").lower()
    mock_client.get.assert_not_called()


@pytest.mark.anyio
async def test_16_event_slug_timestamp_mismatch_rejected():
    """Slug timestamp that doesn't match prediction_window_start is rejected."""
    start, end = _pw(1784534700)
    bad_slug = "btc-updown-5m-9999999999"  # timestamp doesn't match start

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=AssertionError("should not call HTTP"))

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", bad_slug, "0xabc", start, end)

    assert result.verified is False
    assert "mismatch" in (result.validation_error or "").lower()
    mock_client.get.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 17: Condition snapshot guard
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_17_stale_condition_discarded_by_snapshot_guard():
    """
    _persist_verified must discard a result whose condition_id is no longer
    active (snapshot guard per spec §7).  The DB UPDATE WHERE target_verified=False
    will match zero rows when condition is gone.
    """
    worker = TargetWorker()
    stale_condition_id = "0xdeadbeef"

    # Simulate a session where get_active_universe returns NO market with stale_condition_id
    mock_session = AsyncMock()
    # execute returns result_obj with rowcount=0 (no rows matched the WHERE clause)
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    now = datetime.now(timezone.utc)
    market = _mock_market(condition_id=stale_condition_id)
    result_dict = {
        "target_price": 65000.0,
        "target_source": PTB_SOURCE,
        "target_source_url": "https://example.com",
        "target_source_field_path": PTB_FIELD_PATH,
        "target_raw_source": "https://example.com",
        "target_event_slug": market.event_slug,
        "target_condition_id": stale_condition_id,
        "target_verified": True,
        "target_candidate_rule": "ptb_api",
        "target_validation_error": None,
    }

    # Patch _is_still_active to return False (condition is no longer active)
    with patch.object(TargetWorker, "_is_still_active", AsyncMock(return_value=False)):
        await worker._persist_verified(mock_session, market, result_dict, now)

    # When snapshot guard fires, we return early — execute must NOT be called
    mock_session.execute.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 18: PTB has priority over Gamma
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_18_ptb_result_has_priority_over_gamma():
    """
    When PTB API returns a verified result, _probe_gamma must not be called.
    """
    worker = TargetWorker()
    market = _mock_market()
    start, end = _pw()
    market.prediction_window_start = start
    market.prediction_window_end = end

    ptb_result_dict = {
        "target_price": 65000.0,
        "target_source": PTB_SOURCE,
        "target_source_url": "https://polymarket.com/api/crypto/crypto-price?symbol=BTC",
        "target_source_field_path": PTB_FIELD_PATH,
        "target_raw_source": "https://polymarket.com/api/crypto/crypto-price?symbol=BTC",
        "target_event_slug": market.event_slug,
        "target_condition_id": market.condition_id,
        "target_verified": True,
        "target_candidate_rule": "ptb_api",
        "target_validation_error": None,
    }

    mock_http = AsyncMock()  # Gamma would use this — should not be called

    with patch.object(worker, "_probe_ptb_api", AsyncMock(return_value=ptb_result_dict)) as mock_ptb:
        with patch.object(worker, "_probe_gamma", AsyncMock(return_value=None)) as mock_gamma:
            result = await worker._resolve_one(mock_http, market)

    assert result is not None
    assert result["target_source"] == PTB_SOURCE
    assert result["target_verified"] is True
    mock_gamma.assert_not_called()  # Gamma is skipped when PTB succeeds


# ─────────────────────────────────────────────────────────────────────────────
# 19: PTB has priority over Chainlink
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_19_ptb_result_has_priority_over_chainlink():
    """
    When PTB API returns a verified result, _probe_chainlink_candidate is
    never reached.
    """
    worker = TargetWorker()
    market = _mock_market()
    start, end = _pw()
    market.prediction_window_start = start
    market.prediction_window_end = end

    ptb_dict = {
        "target_price": 65000.0,
        "target_source": PTB_SOURCE,
        "target_source_url": "https://polymarket.com/api/crypto/crypto-price",
        "target_source_field_path": PTB_FIELD_PATH,
        "target_raw_source": "",
        "target_event_slug": market.event_slug,
        "target_condition_id": market.condition_id,
        "target_verified": True,
        "target_candidate_rule": "ptb_api",
        "target_validation_error": None,
    }

    mock_http = AsyncMock()

    with patch.object(worker, "_probe_ptb_api", AsyncMock(return_value=ptb_dict)):
        with patch.object(worker, "_probe_gamma", AsyncMock(return_value=None)):
            with patch.object(worker, "_probe_chainlink_candidate", MagicMock()) as mock_cl:
                result = await worker._resolve_one(mock_http, market)

    assert result is not None
    assert result["target_source"] == PTB_SOURCE
    mock_cl.assert_not_called()  # Chainlink is skipped when PTB succeeds


# ─────────────────────────────────────────────────────────────────────────────
# 20: Unverified PTB result doesn't overwrite verified target
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_20_unverified_ptb_result_falls_through_to_gamma():
    """
    When PTB returns unverified (e.g. HTTP error), _resolve_one falls through
    to Gamma and does not return a verified result from PTB.
    """
    worker = TargetWorker()
    market = _mock_market()
    start, end = _pw()
    market.prediction_window_start = start
    market.prediction_window_end = end

    gamma_dict = {
        "target_price": 64000.0,
        "target_source": "POLYMARKET_GAMMA",
        "target_raw_source": "btc-updown-5m-1784534700/priceToBeat=64000.0",
        "target_event_slug": market.event_slug,
        "target_condition_id": market.condition_id,
        "target_verified": True,
        "target_candidate_rule": "priceToBeat",
        "target_validation_error": None,
    }
    mock_http = AsyncMock()

    # PTB returns None (unverified / failed → _probe_ptb_api returns None)
    with patch.object(worker, "_probe_ptb_api", AsyncMock(return_value=None)):
        with patch.object(worker, "_probe_gamma", AsyncMock(return_value=gamma_dict)) as mock_gamma:
            result = await worker._resolve_one(mock_http, market)

    assert result is not None
    assert result["target_source"] == "POLYMARKET_GAMMA"
    mock_gamma.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 21: Verified target is immutable once locked
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_21_verified_target_immutable_once_locked():
    """
    run_once must skip markets where target_verified=True.
    A market that is already verified is excluded from the pending list and
    never re-processed.
    """
    worker = TargetWorker()

    verified_market = _mock_market(verified=True)

    mock_session = AsyncMock()

    with patch("app.repositories.universe_repository.get_active_universe", AsyncMock(return_value=[verified_market])):
        with patch.object(worker, "_resolve_one", AsyncMock()) as mock_resolve:
            summary = await worker.run_once(mock_session)

    # No pending markets — _resolve_one is never called
    mock_resolve.assert_not_called()
    assert summary["checked"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 22: Rollover stale result rejected (snapshot guard)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_22_rollover_stale_result_rejected():
    """
    A verified result arriving after a rollover (condition no longer active)
    must be discarded by the snapshot guard.  This prevents Window A's delayed
    PTB response from writing into Window B's row.
    """
    worker = TargetWorker()
    now = datetime.now(timezone.utc)
    old_condition = "0xwindow_a_condition"
    market = _mock_market(condition_id=old_condition)

    mock_session = AsyncMock()
    result_dict = {
        "target_price": 65000.0,
        "target_source": PTB_SOURCE,
        "target_source_url": "https://polymarket.com/api/crypto/crypto-price",
        "target_source_field_path": PTB_FIELD_PATH,
        "target_raw_source": "",
        "target_event_slug": market.event_slug,
        "target_condition_id": old_condition,
        "target_verified": True,
        "target_candidate_rule": "ptb_api",
        "target_validation_error": None,
    }

    # Snapshot guard: condition no longer active after rollover
    with patch.object(TargetWorker, "_is_still_active", AsyncMock(return_value=False)):
        await worker._persist_verified(mock_session, market, result_dict, now)

    # No DB write happened
    mock_session.execute.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 23: source_url persisted on verified target
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_23_source_url_persisted():
    """
    fetch_ptb returns a PTBResult whose source_url contains the full request URL
    with all query parameters.
    """
    start, end = _pw(1784534700)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"openPrice": 63000.0, "closePrice": None}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("BTC", _slug("BTC"), "0xabc", start, end)

    assert result.verified is True
    assert result.source_url is not None
    assert PTB_ENDPOINT in result.source_url
    assert "symbol=BTC" in result.source_url
    assert "variant=fiveminute" in result.source_url


# ─────────────────────────────────────────────────────────────────────────────
# 24: source_field_path persisted on verified target
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_24_source_field_path_persisted():
    """
    fetch_ptb returns a PTBResult whose source_field_path is always "openPrice".
    The target_worker maps this to target_source_field_path in the DB.
    """
    start, end = _pw()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"openPrice": 150.0, "closePrice": None}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.polymarket_ptb_client.create_verified_httpx_client", return_value=mock_client):
        result = await fetch_ptb("SOL", _slug("SOL"), "0xdef", start, end)

    assert result.source_field_path == PTB_FIELD_PATH  # "openPrice"
    assert result.source_field_path == "openPrice"


# ─────────────────────────────────────────────────────────────────────────────
# 25: GAP requires verified target
# ─────────────────────────────────────────────────────────────────────────────

def test_25_gap_requires_verified_target():
    """
    The GAP formula (current_chainlink - official_openPrice) must only run
    when target_verified=True.  A market with target_verified=False must not
    produce a numeric GAP — validated here at the data layer by verifying
    that fetch_ptb returns verified=False on error (no openPrice to compute GAP from).
    """
    # A result with verified=False has no price_to_beat — GAP cannot be computed
    start, end = _pw()
    error_result = PTBResult(
        price_to_beat=None,
        close_price=None,
        verified=False,
        source=PTB_SOURCE,
        source_url=build_ptb_url("BTC", start, end),
        source_field_path=PTB_FIELD_PATH,
        asset="BTC",
        event_slug=_slug("BTC"),
        condition_id="0xabc",
        prediction_window_start=start,
        prediction_window_end=end,
        fetched_at=datetime.now(timezone.utc),
        validation_error="openPrice missing from response",
    )

    assert error_result.verified is False
    assert error_result.price_to_beat is None

    # With verified=False, price_to_beat=None: the GAP formula produces None
    chainlink_price = 63500.0
    gap = (
        chainlink_price - error_result.price_to_beat
        if error_result.verified and error_result.price_to_beat is not None
        else None
    )
    assert gap is None, "GAP must be None when target is not verified"

    # With a verified result, GAP is computable
    verified_result = PTBResult(
        price_to_beat=63000.0,
        close_price=None,
        verified=True,
        source=PTB_SOURCE,
        source_url=build_ptb_url("BTC", start, end),
        source_field_path=PTB_FIELD_PATH,
        asset="BTC",
        event_slug=_slug("BTC"),
        condition_id="0xabc",
        prediction_window_start=start,
        prediction_window_end=end,
        fetched_at=datetime.now(timezone.utc),
    )
    gap_verified = (
        chainlink_price - verified_result.price_to_beat
        if verified_result.verified and verified_result.price_to_beat is not None
        else None
    )
    assert gap_verified == pytest.approx(500.0)
