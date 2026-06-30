"""
Crypto ticker proxy — fetches 24hr stats from Binance server-side.
GET /api/v1/crypto/ticker — avoids browser CORS restrictions.
"""
import json
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/crypto", tags=["crypto-ticker"])

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


@router.get("/ticker")
async def get_crypto_ticker():
    """Return 24hr ticker data for BTC, ETH, SOL, XRP, BNB from Binance."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                BINANCE_TICKER_URL,
                params={"symbols": json.dumps(SYMBOLS, separators=(",", ":"))},
            )
        if resp.status_code in (403, 429, 451):
            raise HTTPException(status_code=502, detail=f"Binance returned {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        result = []
        for d in data:
            sym = d["symbol"].replace("USDT", "")
            result.append({
                "symbol": sym,
                "price": float(d["lastPrice"]),
                "pct_change": float(d["priceChangePercent"]),
                "high": float(d["highPrice"]),
                "low": float(d["lowPrice"]),
                "volume": float(d["quoteVolume"]),
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Binance fetch failed: {e}")
