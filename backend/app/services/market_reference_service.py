"""
Market Reference Service — Phase Next.

Responsible for fetching the "opening price" (Price to Beat) for each market
from Binance historical candles and persisting it to the database exactly once,
at the moment the market is first discovered.

Architecture:
  Polymarket market (start_time + asset + timeframe)
       ↓
  Binance Historical Candle (klines API, startTime = start_time)
       ↓
  opening_price saved to market_universe table
       ↓
  API returns opening_price
       ↓
  Dashboard reads market.opening_price — no frontend calculation

Design decisions:
  - Fetch is attempted only when start_time is in the past (candle must exist).
  - Upcoming markets (start_time in future) are left as reference_status=PENDING;
    the next sync cycle retries them once their start_time passes.
  - Exactly one fetch per market (skips rows where opening_price IS NOT NULL).
  - Uses a dedicated httpx client per call to avoid shared state with btc_candles.py.
"""

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.database import get_session_factory
from app.services.http_client import create_verified_httpx_client
from app.core.logging import get_logger
from app.repositories.universe_repository import update_market_reference

logger = get_logger(__name__)

# Asset → Binance symbol
ASSET_SYMBOL: dict[str, str] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}

# Timeframe → Binance klines interval
TF_INTERVAL: dict[str, str] = {
    "5m":  "5m",
    "15m": "15m",
    "1H":  "1h",
    "4H":  "4h",
    "1D":  "1d",
    "1W":  "1w",
    "1M":  "1M",
}

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
REQUEST_TIMEOUT = 10.0

# Interval duration in milliseconds — used to align start_time to the candle
# boundary that CONTAINS the market start (floor division).
INTERVAL_DURATION_MS: dict[str, int] = {
    "5m":  5  * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h":  60 * 60 * 1000,
    "4h":  4  * 60 * 60 * 1000,
    "1d":  24 * 60 * 60 * 1000,
    "1w":  7  * 24 * 60 * 60 * 1000,
    "1M":  30 * 24 * 60 * 60 * 1000,  # approximate; Binance handles alignment
}


async def fetch_opening_price(
    asset: str,
    timeframe: str,
    start_time: datetime,
) -> Optional[float]:
    """
    Fetch the Binance klines open price for the candle that begins at start_time.

    Returns the open price as a float, or None if the fetch fails or the
    candle is not yet available (start_time in the future).
    """
    now = datetime.now(timezone.utc)
    if start_time > now:
        logger.debug(
            "[MKT-REF] start_time is in the future — skipping fetch",
            asset=asset,
            timeframe=timeframe,
            start_time=start_time.isoformat(),
        )
        return None

    symbol = ASSET_SYMBOL.get(asset.upper())
    interval = TF_INTERVAL.get(timeframe)
    if not symbol or not interval:
        logger.warning(
            "[MKT-REF] Unknown asset or timeframe — cannot fetch",
            asset=asset,
            timeframe=timeframe,
        )
        return None

    raw_ms = int(start_time.timestamp() * 1000)

    # Align down to the candle boundary that CONTAINS start_time.
    # Binance startTime filters for candles whose open_time >= startTime,
    # so passing a non-aligned timestamp returns the NEXT candle, not the
    # one in effect at market creation.  Floor-dividing by the interval
    # duration gives the open_time of the correct candle.
    interval_ms = INTERVAL_DURATION_MS.get(interval)
    start_ms = (raw_ms // interval_ms) * interval_ms if interval_ms else raw_ms

    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "limit": 1,
    }

    try:
        async with create_verified_httpx_client(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(BINANCE_KLINES_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list) or len(data) == 0:
            logger.warning(
                "[MKT-REF] Binance returned empty candle list",
                symbol=symbol,
                interval=interval,
                start_ms=start_ms,
            )
            return None

        candle = data[0]
        open_price = float(candle[1])  # index 1 = open price

        logger.info(
            "[MKT-REF] Opening price fetched",
            asset=asset,
            timeframe=timeframe,
            open_price=open_price,
            candle_open_time=candle[0],
        )
        return open_price

    except httpx.TimeoutException:
        logger.warning("[MKT-REF] Binance timeout", symbol=symbol, interval=interval)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "[MKT-REF] Binance HTTP error",
            status=exc.response.status_code,
            symbol=symbol,
        )
        return None
    except Exception as exc:
        logger.error("[MKT-REF] Unexpected error fetching candle", error=str(exc))
        return None


async def resolve_market_reference(
    condition_id: str,
    asset: str,
    timeframe: str,
    start_time: Optional[datetime],
) -> None:
    """
    Fetch and persist the opening_price for a market that does not yet have one.

    Skips silently if start_time is None or in the future.
    On success, writes opening_price + metadata and sets reference_status=READY.
    On failure, sets reference_status=PENDING so the next sync cycle retries.
    """
    if start_time is None:
        return

    now = datetime.now(timezone.utc)
    if start_time > now:
        # Not yet started — leave as PENDING, retry after start_time passes.
        return

    opening_price = await fetch_opening_price(asset, timeframe, start_time)

    factory = get_session_factory()
    async with factory() as session:
        if opening_price is not None:
            await update_market_reference(
                session,
                condition_id=condition_id,
                opening_price=opening_price,
                opening_price_source="Binance",
                opening_price_timestamp=start_time,
                reference_status="READY",
            )
        else:
            await update_market_reference(
                session,
                condition_id=condition_id,
                opening_price=None,
                opening_price_source=None,
                opening_price_timestamp=None,
                reference_status="PENDING",
            )
        await session.commit()
