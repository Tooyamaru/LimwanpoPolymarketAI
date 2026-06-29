from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(tags=["btc-candles"])

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
ALLOWED_INTERVALS = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}

@router.get("/btc/candles")
async def get_btc_candles(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="5m"),
    limit: int = Query(default=80, ge=1, le=500),
):
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                BINANCE_KLINES_URL,
                params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Binance fetch failed: {e}")
