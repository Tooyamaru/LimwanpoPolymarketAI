"""
Binance Spot Collector — Sprint 2.

Fetches 24hr ticker data for configured symbols via the public Binance REST API.
No API key required for ticker endpoints.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
REQUEST_TIMEOUT = 10.0


class BinanceTicker(BaseModel):
    symbol: str
    last_price: float = Field(..., alias="lastPrice")
    bid_price: float = Field(..., alias="bidPrice")
    ask_price: float = Field(..., alias="askPrice")
    volume: float = Field(..., alias="volume")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class BinanceSpotData(BaseModel):
    symbol: str
    last_price: float
    bid: float
    ask: float
    volume: float
    timestamp: datetime


class BinanceSpotCollector:
    """
    Collects real-time ticker data from Binance Spot public API.

    Endpoint: GET /api/v3/ticker/24hr
    Returns: lastPrice, bidPrice, askPrice, volume for each symbol.
    """

    def __init__(self, symbols: list[str] = SYMBOLS) -> None:
        self.symbols = symbols
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BINANCE_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def fetch(self) -> list[BinanceSpotData]:
        """
        Fetch ticker data for all configured symbols in a single API call.
        Returns a list of BinanceSpotData, one per symbol.
        """
        client = await self._get_client()

        # Binance accepts a JSON-encoded list of symbols as a query param
        symbols_param = "[" + ",".join(f'"{s}"' for s in self.symbols) + "]"

        try:
            response = await client.get(
                "/api/v3/ticker/24hr",
                params={"symbols": symbols_param},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Binance API HTTP error",
                status_code=exc.response.status_code,
                url=str(exc.request.url),
            )
            raise
        except httpx.RequestError as exc:
            logger.error("Binance API request error", error=str(exc))
            raise

        now = datetime.now(timezone.utc)
        results: list[BinanceSpotData] = []

        for raw in response.json():
            try:
                ticker = BinanceTicker.model_validate(raw)
                results.append(
                    BinanceSpotData(
                        symbol=ticker.symbol,
                        last_price=ticker.last_price,
                        bid=ticker.bid_price,
                        ask=ticker.ask_price,
                        volume=ticker.volume,
                        timestamp=now,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to parse Binance ticker", symbol=raw.get("symbol"), error=str(exc))

        logger.info("Binance Spot fetch complete", symbols=len(results))
        return results

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
