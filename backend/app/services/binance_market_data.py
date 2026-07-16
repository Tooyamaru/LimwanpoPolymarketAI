"""
services/binance_market_data.py — Shared Binance klines client for the
Decision Engine pipeline (Momentum / Trend / Volatility engines).

This is intentionally a *separate* client from btc_candles.py and
market_reference_service.py (dashboard-adjacent, frozen code) so that new
Decision Engine work never touches those files. Read-only: only fetches
public market data from Binance, never writes anywhere.
"""

from typing import Optional

import httpx

from app.core.logging import get_logger
from app.services.http_client import create_verified_httpx_client

logger = get_logger(__name__)

# Asset → Binance symbol
ASSET_SYMBOL: dict[str, str] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}

# Market timeframe → Binance klines interval
TF_INTERVAL: dict[str, str] = {
    "5m": "5m",
    "15m": "15m",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
    "1M": "1M",
}

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
BINANCE_OPEN_INTEREST_URL = "https://fapi.binance.com/fapi/v1/openInterest"
BINANCE_LONG_SHORT_RATIO_URL = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
REQUEST_TIMEOUT = 10.0


async def fetch_klines(asset: str, timeframe: str, limit: int = 100) -> list[dict]:
    """
    Fetch the most recent *limit* candles for asset/timeframe from Binance.

    Returns a list of dicts with keys: open_time, open, high, low, close,
    volume — ordered oldest → newest. Returns [] on any failure or when
    asset/timeframe is not mapped to a known Binance symbol/interval.
    """
    symbol = ASSET_SYMBOL.get(asset.upper())
    interval = TF_INTERVAL.get(timeframe)
    if not symbol or not interval:
        logger.debug(
            "[BINANCE-MD] Unknown asset or timeframe — skipping fetch",
            asset=asset,
            timeframe=timeframe,
        )
        return []

    params = {"symbol": symbol, "interval": interval, "limit": limit}

    try:
        async with create_verified_httpx_client(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(BINANCE_KLINES_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("[BINANCE-MD] Binance timeout", symbol=symbol, interval=interval)
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "[BINANCE-MD] Binance HTTP error",
            status=exc.response.status_code,
            symbol=symbol,
        )
        return []
    except Exception as exc:
        logger.error("[BINANCE-MD] Unexpected error fetching klines", error=str(exc))
        return []

    if not isinstance(data, list):
        return []

    candles: list[dict] = []
    for row in data:
        try:
            candles.append({
                "open_time": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        except (IndexError, TypeError, ValueError):
            continue

    return candles


def closes_of(candles: list[dict]) -> list[float]:
    return [c["close"] for c in candles]


def highs_of(candles: list[dict]) -> list[float]:
    return [c["high"] for c in candles]


def lows_of(candles: list[dict]) -> list[float]:
    return [c["low"] for c in candles]


def volumes_of(candles: list[dict]) -> list[float]:
    return [c["volume"] for c in candles]


def last_close(candles: list[dict]) -> Optional[float]:
    return candles[-1]["close"] if candles else None


async def fetch_order_book_depth(asset: str, limit: int = 100) -> Optional[dict]:
    """
    Fetch Binance spot order book depth for asset — supporting/confirmation
    data only (Orderbook Engine). Returns dict with 'bids' and 'asks', each a
    list of (price, qty) floats, or None on failure / unknown asset.
    """
    symbol = ASSET_SYMBOL.get(asset.upper())
    if not symbol:
        return None

    try:
        async with create_verified_httpx_client(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                BINANCE_DEPTH_URL, params={"symbol": symbol, "limit": limit}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("[BINANCE-MD] Order book depth fetch failed", symbol=symbol, error=str(exc))
        return None

    try:
        bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
    except (ValueError, TypeError):
        return None

    return {"bids": bids, "asks": asks}


async def fetch_funding_data(asset: str) -> Optional[dict]:
    """
    Fetch Binance USDT-M perpetual futures funding rate, open interest, and
    global long/short account ratio for asset — supporting/confirmation data
    only (Funding Engine). Returns None on failure / unknown asset. Any of
    the three sub-fields may individually be None if that endpoint fails.
    """
    symbol = ASSET_SYMBOL.get(asset.upper())
    if not symbol:
        return None

    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    long_short_ratio: Optional[float] = None

    async with create_verified_httpx_client(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(BINANCE_FUNDING_URL, params={"symbol": symbol})
            resp.raise_for_status()
            funding_rate = float(resp.json().get("lastFundingRate"))
        except Exception as exc:
            logger.debug("[BINANCE-MD] Funding rate fetch failed", symbol=symbol, error=str(exc))

        try:
            resp = await client.get(BINANCE_OPEN_INTEREST_URL, params={"symbol": symbol})
            resp.raise_for_status()
            open_interest = float(resp.json().get("openInterest"))
        except Exception as exc:
            logger.debug("[BINANCE-MD] Open interest fetch failed", symbol=symbol, error=str(exc))

        try:
            resp = await client.get(
                BINANCE_LONG_SHORT_RATIO_URL,
                params={"symbol": symbol, "period": "5m", "limit": 1},
            )
            resp.raise_for_status()
            rows = resp.json()
            if isinstance(rows, list) and rows:
                long_short_ratio = float(rows[-1].get("longShortRatio"))
        except Exception as exc:
            logger.debug("[BINANCE-MD] Long/short ratio fetch failed", symbol=symbol, error=str(exc))

    if funding_rate is None and open_interest is None and long_short_ratio is None:
        return None

    return {
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "long_short_ratio": long_short_ratio,
    }
