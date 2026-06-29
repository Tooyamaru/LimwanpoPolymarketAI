"""
╔══════════════════════════════════════════════════════════════════╗
║  BTC CHART MODULE — BACKEND ENDPOINT                            ║
║  Status : PRODUCTION READY / FROZEN                             ║
║                                                                  ║
║  Final configuration:                                            ║
║    • GET /api/v1/btc/candles — proxy to Binance /api/v3/klines  ║
║    • Params: symbol, interval (validated), limit (1–500)         ║
║    • Timeout: 15 s via httpx.AsyncClient                         ║
║    • Error mapping:                                              ║
║        Binance 403  → HTTP 502 (geo-block)                       ║
║        Binance 429  → HTTP 502 (rate-limit)                      ║
║        Binance 451  → HTTP 502 (legal block)                     ║
║        TimeoutException → HTTP 504                               ║
║        ConnectError     → HTTP 502                               ║
║        HTTPStatusError  → HTTP 502                               ║
║    • HTTPException always re-raised (never swallowed)            ║
║    • Full structured logging on every request/response/error     ║
║                                                                  ║
║  Change policy: modify ONLY if a reproducible bug, runtime       ║
║  error, security issue, or Binance API change requires it,       ║
║  OR if explicitly requested.                                     ║
╚══════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import httpx
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["btc-candles"])

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
ALLOWED_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


@router.get("/btc/candles")
async def get_btc_candles(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="5m"),
    limit: int = Query(default=80, ge=1, le=500),
):
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")

    url = BINANCE_KLINES_URL
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    t0 = time.perf_counter()

    logger.info("[BTC-CANDLES] Request started — symbol=%s interval=%s limit=%s", symbol, interval, limit)
    logger.info("[BTC-CANDLES] Binance URL: %s params=%s", url, params)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)

        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.info(
            "[BTC-CANDLES] Binance responded — status=%s elapsed=%dms",
            resp.status_code, elapsed_ms,
        )

        if resp.status_code == 403:
            logger.error("[BTC-CANDLES] Binance HTTP 403 — IP may be geo-blocked or rate-limited")
            raise HTTPException(status_code=502, detail="Binance returned 403 Forbidden — server IP may be geo-blocked")
        if resp.status_code == 429:
            logger.error("[BTC-CANDLES] Binance HTTP 429 — rate limit exceeded")
            raise HTTPException(status_code=502, detail="Binance rate limit exceeded (429)")
        if resp.status_code == 451:
            logger.error("[BTC-CANDLES] Binance HTTP 451 — region blocked")
            raise HTTPException(status_code=502, detail="Binance blocked for legal reasons in this region (451)")

        resp.raise_for_status()
        data = resp.json()

        candle_count = len(data) if isinstance(data, list) else "N/A (not a list)"
        logger.info("[BTC-CANDLES] Candles received: %s", candle_count)
        return data

    except HTTPException:
        # Re-raise our own intentional HTTPExceptions (403/429/451 mappings above)
        # so they are not swallowed by the generic Exception handler below.
        raise
    except httpx.TimeoutException as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error("[BTC-CANDLES] Timeout after %dms — %s", elapsed_ms, e)
        raise HTTPException(status_code=504, detail=f"Binance request timed out after {elapsed_ms}ms")
    except httpx.ConnectError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error("[BTC-CANDLES] Connection error after %dms — %s", elapsed_ms, e)
        raise HTTPException(status_code=502, detail=f"Cannot connect to Binance (DNS/TCP failure): {e}")
    except httpx.HTTPStatusError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "[BTC-CANDLES] HTTP error %s after %dms — %s",
            e.response.status_code, elapsed_ms, e,
        )
        raise HTTPException(status_code=502, detail=f"Binance HTTP {e.response.status_code}: {e}")
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error("[BTC-CANDLES] Unexpected error after %dms — %s: %s", elapsed_ms, type(e).__name__, e)
        raise HTTPException(status_code=502, detail=f"Binance fetch failed ({type(e).__name__}): {e}")
