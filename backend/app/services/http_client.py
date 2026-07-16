"""
Centralized verified HTTP client factory.

Uses the system CA bundle (/etc/ssl/certs/ca-certificates.crt) for TLS
verification, falling back to certifi if available.  SSL verification is
always enabled — verify=False is never used.

Priority for CA bundle resolution:
1. SSL_CERT_FILE or REQUESTS_CA_BUNDLE environment override
2. System CA bundle  (/etc/ssl/certs/ca-certificates.crt)
3. certifi bundle    (if installed and present on disk)

All external HTTPS clients in the project must use
create_verified_httpx_client() instead of constructing
httpx.AsyncClient() directly.
"""

import os
import ssl
from typing import Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"

_STANDARD_HEADERS: dict[str, str] = {
    "User-Agent": "LIMWANPO-AI/1.0",
    "Accept": "application/json",
}


def _resolve_ca_bundle() -> Optional[str]:
    """
    Return the best available CA bundle file path, or None if none found.

    Checks in priority order:
    1. SSL_CERT_FILE env var
    2. REQUESTS_CA_BUNDLE env var
    3. System CA bundle (/etc/ssl/certs/ca-certificates.crt)
    4. certifi CA bundle (if certifi is installed and the file exists)
    """
    for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(env_key, "")
        if path and os.path.isfile(path):
            logger.debug("CA bundle resolved from env", env_key=env_key, path=path)
            return path

    if os.path.isfile(_SYSTEM_CA_BUNDLE):
        return _SYSTEM_CA_BUNDLE

    try:
        import certifi  # type: ignore[import]
        certifi_path = certifi.where()
        if os.path.isfile(certifi_path):
            return certifi_path
    except ImportError:
        pass

    logger.warning(
        "No valid CA bundle found; httpx will use its built-in default",
        tried_system_ca=_SYSTEM_CA_BUNDLE,
    )
    return None


def create_verified_ssl_context() -> ssl.SSLContext:
    """
    Return an ssl.SSLContext backed by the best available CA bundle.
    Certificate verification is always enabled.
    """
    ca_bundle = _resolve_ca_bundle()
    ctx = ssl.create_default_context(cafile=ca_bundle)
    return ctx


def create_verified_httpx_client(
    *,
    base_url: str = "",
    timeout: float = 20.0,
    follow_redirects: bool = True,
    extra_headers: Optional[dict] = None,
) -> httpx.AsyncClient:
    """
    Create a verified httpx.AsyncClient with:
    - System/certifi CA bundle for TLS verification (never verify=False)
    - Standard User-Agent: LIMWANPO-AI/1.0
    - Accept: application/json
    - Configurable base_url, timeout, and follow_redirects

    Always use this factory instead of constructing httpx.AsyncClient()
    directly for any external HTTPS API call.
    """
    ssl_ctx = create_verified_ssl_context()
    headers = dict(_STANDARD_HEADERS)
    if extra_headers:
        headers.update(extra_headers)

    return httpx.AsyncClient(
        base_url=base_url,
        verify=ssl_ctx,
        timeout=timeout,
        headers=headers,
        follow_redirects=follow_redirects,
    )


def classify_httpx_error(exc: Exception) -> str:
    """
    Classify an httpx (or SSL) exception into a short category string.

    Returns one of:
        SSL_ERROR        — TLS/certificate verification failure
        CONNECT_ERROR    — TCP connection refused or DNS resolution failure
        TIMEOUT          — request timed out (connect, read, or pool timeout)
        HTTP_4XX         — server returned a 4xx status code
        HTTP_5XX         — server returned a 5xx status code
        EMPTY_RESPONSE   — successful HTTP but empty/unexpected body
        UNKNOWN          — any other exception type
    """
    if isinstance(exc, httpx.ConnectError):
        exc_str = str(exc).upper()
        if "SSL" in exc_str or "CERTIFICATE" in exc_str or "HANDSHAKE" in exc_str:
            return "SSL_ERROR"
        return "CONNECT_ERROR"
    if isinstance(exc, httpx.TimeoutException):
        return "TIMEOUT"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if 400 <= code < 500:
            return "HTTP_4XX"
        if 500 <= code < 600:
            return "HTTP_5XX"
        return f"HTTP_{code}"
    return "UNKNOWN"
