"""
Chainlink RTDS API — GET /api/v1/chainlink/health
                     GET /api/v1/chainlink/prices
                     GET /api/v1/chainlink/candles

Provides:
  - Connection health with all required state fields
  - Per-asset Chainlink price snapshot (value, age, stale, healthy, source)
  - OHLC candles aggregated from in-memory Chainlink tick history

All data comes exclusively from the in-memory ChainlinkRTDSClient singleton.
No Binance data is returned from these endpoints.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.services.chainlink_client import (
    OFFICIAL_SUBSCRIPTION_PAYLOAD,
    SUBSCRIPTION_PAYLOAD_VERSION,
    SYMBOL_TO_ASSET,
    get_chainlink_client,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chainlink", tags=["chainlink"])


@router.get("/health")
async def get_chainlink_health():
    """
    Return the full connection health of the Chainlink RTDS client.

    State definitions:
      connected   = WebSocket handshake succeeded
      subscribed  = official payload sent successfully
      receiving   = at least one valid update parsed
      healthy     = connected AND subscribed AND receiving
                    AND all primary assets (BTC/ETH/SOL/XRP) are fresh
    """
    client = get_chainlink_client()
    if client is None:
        return {
            "enabled": False,
            "connected": False,
            "subscribed": False,
            "receiving": False,
            "healthy": False,
            "last_message_at": None,
            "last_valid_tick_at": None,
            "reconnect_count": 0,
            "parse_error_count": 0,
            "last_error": None,
            "subscription_payload_version": SUBSCRIPTION_PAYLOAD_VERSION,
            "assets": {},
        }

    from app.config.settings import settings

    assets_health: dict = {}
    for asset in ("BTC", "ETH", "SOL", "XRP"):
        p = client.get_price(asset)
        assets_health[asset] = {
            "has_data": p is not None,
            "stale": p.stale if p else True,
            "age_ms": p.age_ms if p else None,
            "update_count": p.update_count if p else 0,
        }

    last_msg = client.last_message_at
    last_tick = client.last_valid_tick_at

    return {
        "enabled": settings.CHAINLINK_ENABLED,
        "connected": client.connected,
        "subscribed": client.subscribed,
        "receiving": client.receiving,
        "healthy": client.is_healthy(),
        "session_start": client.session_start.isoformat(),
        "last_message_at": last_msg.isoformat() if last_msg else None,
        "last_valid_tick_at": last_tick.isoformat() if last_tick else None,
        "reconnect_count": client.reconnect_count,
        "parse_error_count": client.parse_error_count,
        "last_error": client.last_error,
        "subscription_payload_version": client.subscription_payload_version,
        "stale_threshold_seconds": settings.CHAINLINK_STALE_SECONDS,
        "assets": assets_health,
    }


@router.get("/prices")
async def get_chainlink_prices():
    """
    Return the latest Chainlink RTDS price for every subscribed asset.

    Fields per asset:
      asset                  — BTC | ETH | SOL | XRP
      symbol                 — btc/usd | eth/usd | sol/usd | xrp/usd
      value                  — float price in USD
      full_accuracy_value    — raw string from RTDS payload.full_accuracy_value
      source                 — always "POLYMARKET_RTDS_CHAINLINK"
      source_ts_ms           — Chainlink oracle timestamp (ms)
      source_ts_iso          — ISO 8601 string of source_ts_ms
      age_ms                 — milliseconds since source_ts_ms
      stale                  — true when age_ms > CHAINLINK_STALE_SECONDS × 1000
      connected              — WebSocket connection open
      subscribed             — official payload sent
      receiving              — at least one valid tick received
      healthy                — connected AND subscribed AND receiving AND not stale
      update_count           — total ticks received since startup
      session_start          — ISO timestamp when the RTDS client started

    Returns an empty object {} when the client is not yet initialised.
    No Binance data is present in this response.
    """
    client = get_chainlink_client()
    if client is None:
        return {}

    prices = client.get_all_prices()
    session_start_iso = client.session_start.isoformat()

    result: dict = {}
    for asset, p in prices.items():
        result[asset] = {
            "asset": p.asset,
            "symbol": p.symbol,
            "value": p.value,
            "full_accuracy_value": p.full_accuracy_value,
            "source": p.source,
            "source_ts_ms": p.source_ts_ms,
            "source_ts_iso": p.source_ts_iso,
            "age_ms": p.age_ms,
            "stale": p.stale,
            "connected": p.connected,
            "subscribed": p.subscribed,
            "receiving": p.receiving,
            "healthy": p.healthy,
            "update_count": p.update_count,
            "session_start": session_start_iso,
        }

    # Include stubs for assets not yet reported
    asset_to_sym = {v: k for k, v in SYMBOL_TO_ASSET.items()}
    for asset in SYMBOL_TO_ASSET.values():
        if asset not in result:
            result[asset] = {
                "asset": asset,
                "symbol": asset_to_sym.get(asset, ""),
                "value": None,
                "full_accuracy_value": None,
                "source": "POLYMARKET_RTDS_CHAINLINK",
                "source_ts_ms": None,
                "source_ts_iso": None,
                "age_ms": None,
                "stale": True,
                "connected": client.connected,
                "subscribed": client.subscribed,
                "receiving": client.receiving,
                "healthy": False,
                "update_count": 0,
                "session_start": session_start_iso,
            }

    return result


@router.get("/candles")
async def get_chainlink_candles(
    asset: str = Query("BTC", description="Asset symbol: BTC | ETH | SOL | XRP"),
    interval: int = Query(300, description="Candle interval in seconds (default 300 = 5m)"),
    limit: int = Query(80, description="Maximum number of candles to return"),
):
    """
    Return OHLC candles aggregated from in-memory Chainlink RTDS tick history.

    Candles are built entirely from ticks received since application startup.
    No Binance data is used — not for seeding, not as fallback.

    If the client has been running for less than one full candle interval, the
    response will contain fewer candles than *limit*.

    Fields:
      candles       — list of {time, open, high, low, close, tick_count}
                      time = Unix seconds (candle open), ordered oldest-first
      asset         — as requested
      interval      — as requested (seconds)
      session_start — ISO timestamp when tick history begins (RTDS only)
      connected     — WebSocket connection state
      subscribed    — subscription state
      receiving     — valid data received flag
      healthy       — overall health flag
      source        — always "POLYMARKET_RTDS_CHAINLINK"

    When no candles are available yet, returns candles=[] and session_start
    so the frontend can display "CHAINLINK SESSION DATA / STARTED AT HH:MM:SS".
    Volume is not available from RTDS; tick_count is provided instead.
    """
    client = get_chainlink_client()

    asset = asset.upper()

    if client is None:
        return {
            "candles": [],
            "asset": asset,
            "interval": interval,
            "session_start": None,
            "connected": False,
            "subscribed": False,
            "receiving": False,
            "healthy": False,
            "source": "POLYMARKET_RTDS_CHAINLINK",
            "message": "CHAINLINK_CLIENT_NOT_STARTED",
        }

    candles = client.get_candles(asset=asset, interval_seconds=interval, limit=limit)
    session_start_iso = client.session_start.isoformat()
    latest = client.get_price(asset)

    return {
        "candles": [
            {
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "tick_count": c.tick_count,
            }
            for c in candles
        ],
        "asset": asset,
        "interval": interval,
        "session_start": session_start_iso,
        "connected": client.connected,
        "subscribed": client.subscribed,
        "receiving": client.receiving,
        "healthy": client.is_healthy(),
        "source": "POLYMARKET_RTDS_CHAINLINK",
        "current_price": latest.value if latest else None,
        "message": (
            f"CHAINLINK SESSION DATA\nSTARTED AT {session_start_iso}"
            if not candles
            else "OK"
        ),
    }
