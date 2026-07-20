"""
PolymarketPTBClient — Official Polymarket Crypto Price API client.

Fetches the official Price to Beat (openPrice) from the confirmed endpoint:

  GET https://polymarket.com/api/crypto/crypto-price
      ?symbol=<BTC|ETH|SOL|XRP>
      &eventStartTime=<prediction_window_start UTC ISO-8601>
      &endDate=<prediction_window_end UTC ISO-8601>
      &variant=fiveminute

Confirmed working for BTC, ETH, SOL, XRP.
Response: { "openPrice": <float>, "closePrice": <float|null> }

Design decisions:
  - verified=True only when HTTP 200, JSON object, openPrice is numeric > 0,
    window duration == 300s, and event_slug timestamp matches pw_start.
  - verified=False for any failure — caller stores as pending, never as
    an auto-verified target.
  - closePrice may be null while the current window is still active; this is
    accepted and returned as-is.
  - Uses create_verified_httpx_client() for all outbound HTTPS calls.
  - source = "POLYMARKET_CRYPTO_PRICE_API"
  - source_field_path = "openPrice"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.services.http_client import create_verified_httpx_client

logger = get_logger(__name__)

# Official Polymarket Crypto Price API endpoint (confirmed)
PTB_ENDPOINT = "https://polymarket.com/api/crypto/crypto-price"
PTB_SOURCE = "POLYMARKET_CRYPTO_PRICE_API"
PTB_FIELD_PATH = "openPrice"

# Expected prediction window duration in seconds (5-minute markets = 300 s)
EXPECTED_WINDOW_SECONDS = 300

# Supported assets
SUPPORTED_ASSETS = frozenset({"BTC", "ETH", "SOL", "XRP"})


@dataclass
class PTBResult:
    """
    Result returned by fetch_ptb() for one prediction-window market.

    When verified=True all numeric fields are populated and the target is
    ready to lock.  When verified=False, price_to_beat is None and
    validation_error describes the reason.
    """

    # ── Core result ───────────────────────────────────────────────────────────
    price_to_beat: Optional[float]
    close_price: Optional[float]
    verified: bool

    # ── Source metadata (persisted for audit trail) ───────────────────────────
    source: str
    source_url: str          # full URL including query params
    source_field_path: str   # always "openPrice"

    # ── Market identity ───────────────────────────────────────────────────────
    asset: str
    event_slug: Optional[str]
    condition_id: str
    prediction_window_start: datetime
    prediction_window_end: datetime

    # ── Timestamps ────────────────────────────────────────────────────────────
    fetched_at: datetime

    # ── Error detail when not verified ────────────────────────────────────────
    validation_error: Optional[str] = field(default=None)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_iso_utc(dt: datetime) -> str:
    """
    Format a datetime as exact UTC ISO-8601 string.
    Example: 2026-07-20T07:00:00Z
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Normalise to UTC before formatting
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_ptb_url(
    asset: str,
    prediction_window_start: datetime,
    prediction_window_end: datetime,
) -> str:
    """
    Build the full PTB request URL including query parameters.

    Exposed as a public function so tests can verify URL construction without
    making a network call.
    """
    symbol = asset.upper()
    event_start = _format_iso_utc(prediction_window_start)
    end_date = _format_iso_utc(prediction_window_end)
    return (
        f"{PTB_ENDPOINT}"
        f"?symbol={symbol}"
        f"&eventStartTime={event_start}"
        f"&variant=fiveminute"
        f"&endDate={end_date}"
    )


def _validate_inputs(
    asset: str,
    prediction_window_start: datetime,
    prediction_window_end: datetime,
    event_slug: Optional[str],
) -> Optional[str]:
    """
    Pre-flight validation.

    Returns an error string on failure, None on success.
    Does NOT make network calls.
    """
    # Asset must be in the supported set
    if asset.upper() not in SUPPORTED_ASSETS:
        return f"Unsupported asset: {asset!r} — expected one of {sorted(SUPPORTED_ASSETS)}"

    # Both datetimes must be timezone-aware
    if prediction_window_start.tzinfo is None:
        return "prediction_window_start must be timezone-aware"
    if prediction_window_end.tzinfo is None:
        return "prediction_window_end must be timezone-aware"

    # Window duration must be exactly EXPECTED_WINDOW_SECONDS (≤0.5 s tolerance)
    duration = (prediction_window_end - prediction_window_start).total_seconds()
    if abs(duration - EXPECTED_WINDOW_SECONDS) > 0.5:
        return (
            f"Window duration must be exactly {EXPECTED_WINDOW_SECONDS}s "
            f"(got {duration:.3f}s)"
        )

    # Event slug timestamp (last segment) must match prediction_window_start unix ts
    if event_slug is not None:
        parts = event_slug.rsplit("-", 1)
        if len(parts) == 2:
            try:
                slug_ts = int(parts[1])
                expected_ts = int(prediction_window_start.timestamp())
                if slug_ts != expected_ts:
                    return (
                        f"Event slug timestamp mismatch: "
                        f"slug last segment is {slug_ts}, "
                        f"prediction_window_start unix is {expected_ts}"
                    )
            except (ValueError, TypeError):
                # Slug doesn't have a parseable integer suffix — not a hard reject
                pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_ptb(
    asset: str,
    event_slug: Optional[str],
    condition_id: str,
    prediction_window_start: datetime,
    prediction_window_end: datetime,
) -> PTBResult:
    """
    Fetch the official Price to Beat for one prediction-window market.

    Parameters
    ----------
    asset
        One of BTC, ETH, SOL, XRP (case-insensitive).
    event_slug
        Exact rolling event slug, e.g. "btc-updown-5m-1784534700".
        Used for validation (slug timestamp must match pw_start).
    condition_id
        Polymarket condition ID — carried through for identity verification.
    prediction_window_start
        UTC-aware datetime for the window open time (= eventStartTime).
    prediction_window_end
        UTC-aware datetime for the window close time (= endDate).

    Returns
    -------
    PTBResult
        verified=True and price_to_beat populated on success.
        verified=False with validation_error on any failure.
    """
    now = datetime.now(timezone.utc)
    asset_upper = asset.upper()

    source_url = build_ptb_url(asset_upper, prediction_window_start, prediction_window_end)

    def _fail(error: str) -> PTBResult:
        return PTBResult(
            price_to_beat=None,
            close_price=None,
            verified=False,
            source=PTB_SOURCE,
            source_url=source_url,
            source_field_path=PTB_FIELD_PATH,
            asset=asset_upper,
            event_slug=event_slug,
            condition_id=condition_id,
            prediction_window_start=prediction_window_start,
            prediction_window_end=prediction_window_end,
            fetched_at=now,
            validation_error=error,
        )

    # ── Pre-flight validation (no network) ───────────────────────────────────
    pre_error = _validate_inputs(
        asset_upper,
        prediction_window_start,
        prediction_window_end,
        event_slug,
    )
    if pre_error:
        logger.warning(
            "[PTB] Pre-flight validation failed",
            asset=asset_upper,
            event_slug=event_slug,
            error=pre_error,
        )
        return _fail(pre_error)

    # ── HTTP request ─────────────────────────────────────────────────────────
    params = {
        "symbol": asset_upper,
        "eventStartTime": _format_iso_utc(prediction_window_start),
        "variant": "fiveminute",
        "endDate": _format_iso_utc(prediction_window_end),
    }

    try:
        async with create_verified_httpx_client() as http:
            resp = await http.get(PTB_ENDPOINT, params=params, timeout=10.0)
    except Exception as exc:
        logger.warning(
            "[PTB] HTTP request failed",
            asset=asset_upper,
            event_slug=event_slug,
            error=str(exc),
        )
        return _fail(f"HTTP request failed: {exc}")

    # ── HTTP status ───────────────────────────────────────────────────────────
    if resp.status_code != 200:
        logger.warning(
            "[PTB] Non-200 HTTP status",
            asset=asset_upper,
            event_slug=event_slug,
            status_code=resp.status_code,
        )
        return _fail(f"HTTP {resp.status_code}")

    # ── JSON parse ────────────────────────────────────────────────────────────
    try:
        data = resp.json()
    except Exception as exc:
        logger.warning(
            "[PTB] JSON parse failed",
            asset=asset_upper,
            error=str(exc),
        )
        return _fail(f"JSON parse error: {exc}")

    if not isinstance(data, dict):
        return _fail(f"Expected JSON object, got {type(data).__name__}")

    # ── openPrice validation ──────────────────────────────────────────────────
    open_price_raw = data.get("openPrice")
    if open_price_raw is None:
        logger.warning(
            "[PTB] openPrice missing from response",
            asset=asset_upper,
            event_slug=event_slug,
            response_keys=list(data.keys()),
        )
        return _fail("openPrice missing from response")

    try:
        open_price = float(open_price_raw)
    except (TypeError, ValueError):
        return _fail(f"openPrice is not numeric: {open_price_raw!r}")

    if open_price <= 0:
        return _fail(f"openPrice must be > 0, got {open_price}")

    # ── closePrice (may be null for active windows) ───────────────────────────
    close_price_raw = data.get("closePrice")
    close_price: Optional[float] = None
    if close_price_raw is not None:
        try:
            close_price = float(close_price_raw)
        except (TypeError, ValueError):
            close_price = None  # Treat invalid closePrice as null — not fatal

    logger.info(
        "[PTB] Official Price to Beat fetched",
        asset=asset_upper,
        event_slug=event_slug,
        condition_id=condition_id[:12] if condition_id else None,
        open_price=open_price,
        close_price=close_price,
        source_url=source_url,
    )

    return PTBResult(
        price_to_beat=open_price,
        close_price=close_price,
        verified=True,
        source=PTB_SOURCE,
        source_url=source_url,
        source_field_path=PTB_FIELD_PATH,
        asset=asset_upper,
        event_slug=event_slug,
        condition_id=condition_id,
        prediction_window_start=prediction_window_start,
        prediction_window_end=prediction_window_end,
        fetched_at=now,
        validation_error=None,
    )
