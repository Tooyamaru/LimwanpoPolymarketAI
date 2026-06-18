"""
Polymarket CLOB Collector — Sprint 2.

Fetches active prediction markets from the Polymarket CLOB REST API.
Filters to asset + timeframe markets relevant to the quant strategy.
No API key required for public market data.
"""

import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

CLOB_BASE_URL = "https://clob.polymarket.com"
REQUEST_TIMEOUT = 15.0
PAGE_SIZE = 100

ASSET_KEYWORDS = ["BTC", "ETH", "SOL", "XRP"]
TIMEFRAME_KEYWORDS = ["5m", "15m", "1H", "1h", "5 min", "15 min", "1 hour", "1-hour"]

# Normalised timeframe labels we actually store
TIMEFRAME_MAP = {
    "5m": "5m",
    "5 min": "5m",
    "15m": "15m",
    "15 min": "15m",
    "1h": "1H",
    "1H": "1H",
    "1 hour": "1H",
    "1-hour": "1H",
}


class PolymarketToken(BaseModel):
    token_id: str = Field(..., alias="token_id")
    outcome: str
    price: float = 0.0

    model_config = {"populate_by_name": True}


class PolymarketMarketRaw(BaseModel):
    condition_id: str
    question: str
    description: Optional[str] = None
    tokens: list[PolymarketToken] = Field(default_factory=list)
    liquidity: float = 0.0
    volume: float = 0.0
    end_date_iso: Optional[str] = Field(None, alias="end_date_iso")
    active: bool = True

    model_config = {"populate_by_name": True}


class PolymarketMarketData(BaseModel):
    market_id: str
    title: str
    asset: str
    timeframe: str
    yes_price: float
    no_price: float
    liquidity: float
    volume: float
    end_time: Optional[datetime]
    timestamp: datetime


def _extract_asset(title: str) -> Optional[str]:
    for asset in ASSET_KEYWORDS:
        if asset.upper() in title.upper():
            return asset
    return None


def _extract_timeframe(title: str) -> Optional[str]:
    for keyword, label in TIMEFRAME_MAP.items():
        if re.search(re.escape(keyword), title, re.IGNORECASE):
            return label
    return None


def _parse_price(tokens: list[PolymarketToken], outcome: str) -> float:
    for token in tokens:
        if token.outcome.upper() == outcome.upper():
            return token.price
    return 0.0


class PolymarketCollector:
    """
    Collects active prediction markets from Polymarket CLOB API.

    Discovery: paginates through /markets, filters by asset + timeframe keywords.
    Prices: extracted from embedded token data (Yes / No outcomes).
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=CLOB_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def _fetch_page(self, next_cursor: str = "") -> tuple[list[dict], str]:
        """Fetch one page of markets. Returns (data_list, next_cursor)."""
        client = await self._get_client()
        params: dict = {"limit": PAGE_SIZE, "active": "true"}
        if next_cursor:
            params["next_cursor"] = next_cursor

        try:
            response = await client.get("/markets", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Polymarket API HTTP error",
                status_code=exc.response.status_code,
                url=str(exc.request.url),
            )
            raise
        except httpx.RequestError as exc:
            logger.error("Polymarket API request error", error=str(exc))
            raise

        body = response.json()
        # CLOB API wraps results in {"data": [...], "next_cursor": "..."}
        if isinstance(body, dict):
            return body.get("data", []), body.get("next_cursor", "")
        # Some endpoints return a plain list
        return body, ""

    async def fetch(self) -> list[PolymarketMarketData]:
        """
        Discover and return all active markets matching asset + timeframe filters.
        Paginates automatically until no more pages remain.
        """
        now = datetime.now(timezone.utc)
        results: list[PolymarketMarketData] = []
        next_cursor = ""
        pages = 0
        max_pages = 20  # safety cap

        while pages < max_pages:
            raw_list, next_cursor = await self._fetch_page(next_cursor)
            pages += 1

            for raw in raw_list:
                try:
                    market = PolymarketMarketRaw.model_validate(raw)
                    title = market.question

                    asset = _extract_asset(title)
                    timeframe = _extract_timeframe(title)

                    if not asset or not timeframe:
                        continue

                    yes_price = _parse_price(market.tokens, "Yes")
                    no_price = _parse_price(market.tokens, "No")
                    if yes_price == 0.0 and no_price == 0.0:
                        no_price = round(1.0 - yes_price, 4)

                    end_time: Optional[datetime] = None
                    if market.end_date_iso:
                        try:
                            end_time = datetime.fromisoformat(
                                market.end_date_iso.replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    results.append(
                        PolymarketMarketData(
                            market_id=market.condition_id,
                            title=title,
                            asset=asset,
                            timeframe=timeframe,
                            yes_price=yes_price,
                            no_price=no_price,
                            liquidity=market.liquidity,
                            volume=market.volume,
                            end_time=end_time,
                            timestamp=now,
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to parse Polymarket market", error=str(exc))

            if not next_cursor or next_cursor == "LTE=":
                break

        logger.info(
            "Polymarket fetch complete",
            pages_fetched=pages,
            markets_matched=len(results),
        )
        return results

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
