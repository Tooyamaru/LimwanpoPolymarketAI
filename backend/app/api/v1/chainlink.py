"""
Chainlink RTDS API — GET /api/v1/chainlink/prices
                     GET /api/v1/chainlink/candles

Provides:
  - Per-asset Chainlink price snapshot (value, age, stale, healthy, source)
  - OHLC candles aggregated from in-memory Chainlink tick history for BTC/USD

All data comes exclusively from the in-memory ChainlinkRTDSClient singleton.
No Binance data is returned from these endpoints.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.services.chainlink_client import SYMBOL_TO_ASSET, get_chainlink_client
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chainlink", tags=["chainlink"])


@router.get("/prices")
async def get_chainlink_prices():
    """
    Return the latest Chainlink RTDS price for every subscribed asset.

    Fields per asset:
      asset         — BTC | ETH | SOL | XRP
      symbol        — btc/usd | eth/usd | sol/usd | xrp/usd
      value         — float price in USD
      source        — always "POLYMARKET_RTDS_CHAINLINK"
      source_ts_ms  — Chainlink oracle timestamp (ms)
      source_ts_iso — ISO 8601 string of source_ts_ms
      age_ms        — milliseconds since source_ts_ms
      stale         — true when age_ms > CHAINLINK_STALE_SECONDS × 1000
      connected     — WebSocket connection open
      subscribed    — subscription confirmed by server
      healthy       — connected AND subscribed AND not stale
      update_count  — total ticks received since startup
      session_start — ISO timestamp when the RTDS client started

    Returns an empty object {} when the client is not yet initialised.
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
            "source": p.source,
            "source_ts_ms": p.source_ts_ms,
            "source_ts_iso": p.source_ts_iso,
            "age_ms": p.age_ms,
            "stale": p.stale,
            "connected": p.connected,
            "subscribed": p.subscribed,
            "healthy": p.healthy,
            "update_count": p.update_count,
            "session_start": session_start_iso,
        }

    # Include empty stubs for assets not yet reported
    for asset in SYMBOL_TO_ASSET.values():
        if asset not in result:
            result[asset] = {
                "asset": asset,
                "symbol": SYMBOL_TO_ASSET.get(
                    next((s for s, a in SYMBOL_TO_ASSET.items() if a == asset), ""), ""
                ),
                "value": None,
                "source": "POLYMARKET_RTDS_CHAINLINK",
                "source_ts_ms": None,
                "source_ts_iso": None,
                "age_ms": None,
                "stale": True,
                "connected": client.connected,
                "subscribed": client.subscribed,
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
    If the client has been running for less than one full candle interval, the
    response will contain fewer candles than *limit*.

    Fields:
      candles      — list of {time, open, high, low, close, tick_count}
                     time = Unix seconds (candle open), ordered oldest-first
      asset        — as requested
      interval     — as requested (seconds)
      session_start — ISO timestamp when tick history begins
      connected    — WebSocket connection state
      subscribed   — subscription state
      healthy      — overall health flag

    When no candles are available yet, returns candles=[] and the client
    health / session_start so the frontend can display "DATA STARTED AT".
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
            "healthy": False,
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
        "healthy": client.is_healthy(),
        "current_price": latest.value if latest else None,
        "message": (
            f"DATA STARTED AT {session_start_iso}"
            if not candles
            else "OK"
        ),
    }


@router.get("/health")
async def get_chainlink_health():
    """
    Return the connection health of the Chainlink RTDS client.
    """
    client = get_chainlink_client()
    if client is None:
        return {
            "enabled": False,
            "connected": False,
            "subscribed": False,
            "healthy": False,
            "assets": {},
        }

    from app.config.settings import settings
    assets_health = {}
    for asset in ("BTC", "ETH", "SOL", "XRP"):
        p = client.get_price(asset)
        assets_health[asset] = {
            "has_data": p is not None,
            "stale": p.stale if p else True,
            "age_ms": p.age_ms if p else None,
            "update_count": p.update_count if p else 0,
        }

    return {
        "enabled": settings.CHAINLINK_ENABLED,
        "connected": client.connected,
        "subscribed": client.subscribed,
        "healthy": client.is_healthy(),
        "session_start": client.session_start.isoformat(),
        "stale_threshold_seconds": settings.CHAINLINK_STALE_SECONDS,
        "assets": assets_health,
    }
