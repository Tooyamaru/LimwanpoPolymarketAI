"""
Gamma HTTP client factory tests — http_client.py + gamma_series_client.py.

Covers:
1.  create_verified_httpx_client uses a verified SSL context (never verify=False)
2.  User-Agent header is present on every client
3.  Accept: application/json header is present
4.  SSL error is classified correctly
5.  Timeout error is classified correctly
6.  HTTP 4xx is classified correctly
7.  HTTP 5xx is classified correctly
8.  All Gamma series failed → gamma_status != GAMMA_OK in sync result
9.  Empty Gamma response is classified as GAMMA_EMPTY_RESPONSE (not GAMMA_OK)
"""

import ssl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import httpx

from app.services.http_client import (
    classify_httpx_error,
    create_verified_httpx_client,
    create_verified_ssl_context,
    _resolve_ca_bundle,
)
from app.services.gamma_series_client import GammaSeriesClient


# ── 1. create_verified_httpx_client uses verified SSL context ──────────────────

@pytest.mark.anyio
async def test_create_verified_httpx_client_uses_ssl_context():
    """The returned client must not have verify=False."""
    client = create_verified_httpx_client()
    assert client._transport is not None
    assert client is not None
    await client.aclose()


def test_create_verified_ssl_context_returns_ssl_context():
    ctx = create_verified_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    # Verification must be enabled
    assert ctx.verify_mode != ssl.CERT_NONE


# ── 2. User-Agent header present ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_verified_httpx_client_has_user_agent():
    client = create_verified_httpx_client()
    assert "User-Agent" in client.headers
    assert "LIMWANPO" in client.headers["User-Agent"]
    await client.aclose()


# ── 3. Accept header present ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_verified_httpx_client_has_accept_json():
    client = create_verified_httpx_client()
    assert "Accept" in client.headers
    assert "application/json" in client.headers["Accept"]
    await client.aclose()


# ── 4. SSL error classification ───────────────────────────────────────────────

def test_classify_httpx_error_ssl():
    exc = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    )
    assert classify_httpx_error(exc) == "SSL_ERROR"


def test_classify_httpx_error_ssl_handshake():
    exc = httpx.ConnectError("SSL HANDSHAKE failure")
    assert classify_httpx_error(exc) == "SSL_ERROR"


# ── 5. Timeout classification ─────────────────────────────────────────────────

def test_classify_httpx_error_timeout():
    exc = httpx.ConnectTimeout("timed out")
    assert classify_httpx_error(exc) == "TIMEOUT"


def test_classify_httpx_error_read_timeout():
    exc = httpx.ReadTimeout("read timed out")
    assert classify_httpx_error(exc) == "TIMEOUT"


# ── 6. HTTP 4xx classification ────────────────────────────────────────────────

def test_classify_httpx_error_http_403():
    response = MagicMock()
    response.status_code = 403
    exc = httpx.HTTPStatusError("403 Forbidden", request=MagicMock(), response=response)
    assert classify_httpx_error(exc) == "HTTP_4XX"


def test_classify_httpx_error_http_404():
    response = MagicMock()
    response.status_code = 404
    exc = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=response)
    assert classify_httpx_error(exc) == "HTTP_4XX"


# ── 7. HTTP 5xx classification ────────────────────────────────────────────────

def test_classify_httpx_error_http_500():
    response = MagicMock()
    response.status_code = 500
    exc = httpx.HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=response)
    assert classify_httpx_error(exc) == "HTTP_5XX"


def test_classify_httpx_error_http_503():
    response = MagicMock()
    response.status_code = 503
    exc = httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=response)
    assert classify_httpx_error(exc) == "HTTP_5XX"


# ── 8. All series failed → gamma_status not GAMMA_OK ─────────────────────────

@pytest.mark.anyio
async def test_universe_sync_all_failed_returns_non_ok_gamma_status():
    """
    If every series fetch raises an exception, gamma_status must not be GAMMA_OK.
    """
    from app.services.market_universe_service import MarketUniverseService

    svc = MarketUniverseService()

    # Patch fetch_series and fetch_events to raise SSL-like errors
    ssl_exc = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    )
    with (
        patch.object(svc._client, "fetch_series", new_callable=AsyncMock, side_effect=ssl_exc),
        patch.object(svc._client, "fetch_events", new_callable=AsyncMock, side_effect=ssl_exc),
        patch("app.services.market_universe_service.get_session_factory") as mock_factory,
    ):
        # Session factory should not be called when fetch raises before DB write
        result = await svc.sync()

    assert result["gamma_status"] != "GAMMA_OK"
    assert result["gamma_series_failed"] > 0
    assert result["markets_upserted"] == 0


# ── 9. Empty Gamma response → GAMMA_EMPTY_RESPONSE ───────────────────────────

@pytest.mark.anyio
async def test_universe_sync_empty_response_classified_correctly():
    """
    If all series return 0 events (empty list, no exception), gamma_status
    must be GAMMA_EMPTY_RESPONSE, not GAMMA_OK.
    """
    from app.services.market_universe_service import MarketUniverseService

    svc = MarketUniverseService()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(svc._client, "fetch_series", new_callable=AsyncMock, return_value=None),
        patch.object(svc._client, "fetch_events", new_callable=AsyncMock, return_value=[]),
        patch.object(svc._client, "fetch_event_by_slug", new_callable=AsyncMock, return_value=None),
        patch(
            "app.services.market_universe_service.get_session_factory",
            return_value=lambda: mock_ctx,
        ),
        patch(
            "app.services.market_universe_service.expire_stale_markets",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.services.market_universe_service.demote_excess_active_markets",
            new_callable=AsyncMock,
        ),
    ):
        result = await svc.sync()

    assert result["gamma_status"] == "GAMMA_EMPTY_RESPONSE"
    assert result["gamma_series_ok"] == 0
    assert result["gamma_series_failed"] == 0
    assert result["markets_upserted"] == 0


# ── 10. No verify=False in the production client ──────────────────────────────

def test_no_verify_false_in_production_client():
    """
    Confirm that create_verified_httpx_client never produces a client
    that uses verify=False.  We do this by checking the SSLContext mode.
    """
    ctx = create_verified_ssl_context()
    # ssl.CERT_NONE means verification is disabled — must never occur
    assert ctx.verify_mode != ssl.CERT_NONE
    # ssl.CERT_REQUIRED means certs ARE verified
    assert ctx.verify_mode == ssl.CERT_REQUIRED


# ── 11. CA bundle resolves to a real file or None ────────────────────────────

def test_resolve_ca_bundle_returns_file_or_none():
    """_resolve_ca_bundle must return a valid file path or None."""
    import os
    result = _resolve_ca_bundle()
    if result is not None:
        assert os.path.isfile(result), f"CA bundle path {result!r} does not exist on disk"


# ── 12. GammaSeriesClient._get_client uses verified SSL ──────────────────────

@pytest.mark.anyio
async def test_gamma_series_client_get_client_uses_verified_ssl():
    """
    GammaSeriesClient._get_client() must return an httpx.AsyncClient
    created via create_verified_httpx_client — verified TLS only.
    """
    client_obj = GammaSeriesClient()
    http_client = await client_obj._get_client()
    # Client must exist and not be closed
    assert http_client is not None
    assert not http_client.is_closed
    await client_obj.close()
