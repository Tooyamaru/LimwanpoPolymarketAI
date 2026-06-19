"""
Polymarket CLOB API client — Sprint 9.

Fetches live bid/ask prices for YES and NO tokens from the CLOB.

Endpoints used:
  GET https://clob.polymarket.com/markets/{condition_id}
      → token prices (tokens[].price), volume, liquidity, active/closed flags

  GET https://clob.polymarket.com/book?token_id={token_id}
      → order book bids[] and asks[] for best bid/ask

Retry: exponential back-off (3 attempts).
Timeout: 15 s per request.
Rate limit: 0.1 s delay between requests (burst protection).
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

CLOB_BASE_URL = "https://clob.polymarket.com"
REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RATE_LIMIT_DELAY = 0.10


@dataclass
class OrderBookSide:
    best_bid: Optional[float]
    best_ask: Optional[float]


@dataclass
class ClobMarketData:
    condition_id: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]

    yes_bid: Optional[float]
    yes_ask: Optional[float]
    yes_mid: Optional[float]

    no_bid: Optional[float]
    no_ask: Optional[float]
    no_mid: Optional[float]

    spread_yes: Optional[float]
    spread_no: Optional[float]

    volume: Optional[float]
    liquidity: Optional[float]

    active: bool
    closed: bool


class ClobClient:
    """
    Async HTTP client for the Polymarket CLOB API.

    Usage::

        async with ClobClient() as client:
            data = await client.get_market(condition_id, yes_token_id, no_token_id)
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=CLOB_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def _get_json(self, path: str, params: Optional[dict] = None) -> Optional[dict | list]:
        """GET with retry, returning parsed JSON or None on failure."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.get(path, params=params or {})
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "CLOB request failed, retrying",
                    attempt=attempt,
                    path=path,
                    error=str(exc),
                    wait_seconds=wait,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)

        logger.error("CLOB request exhausted retries", path=path, error=str(last_exc))
        return None

    async def _fetch_order_book(self, token_id: str) -> OrderBookSide:
        """
        Fetch the order book for a single token and return best bid/ask.

        The Polymarket CLOB /book endpoint returns bids in ASCENDING price
        order (lowest price first) and asks in DESCENDING price order (highest
        price first).  Therefore:
          - best bid  = bids[-1]  (highest price = last element)
          - best ask  = asks[-1]  (lowest price  = last element)

        DEF-001 fix (Sprint 9.4): corrected from bids[0]/asks[0] which
        returned the worst bid (0.01) and worst ask (0.99).
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        data = await self._get_json("/book", {"token_id": token_id})
        if not isinstance(data, dict):
            return OrderBookSide(best_bid=None, best_ask=None)

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        best_bid: Optional[float] = None
        best_ask: Optional[float] = None

        if bids:
            try:
                best_bid = float(bids[-1]["price"])
            except (KeyError, ValueError, TypeError):
                pass

        if asks:
            try:
                best_ask = float(asks[-1]["price"])
            except (KeyError, ValueError, TypeError):
                pass

        return OrderBookSide(best_bid=best_bid, best_ask=best_ask)

    async def get_market(
        self,
        condition_id: str,
        yes_token_id: Optional[str] = None,
        no_token_id: Optional[str] = None,
    ) -> Optional[ClobMarketData]:
        """
        Fetch live price data for a single market.

        Steps:
          1. GET /markets/{condition_id} → token prices, volume, liquidity
          2. GET /book?token_id={yes_token_id} → YES best bid/ask
          3. GET /book?token_id={no_token_id}  → NO best bid/ask (if token known)
          4. Compute mids and spreads

        Returns None if the market endpoint fails or the market is not found.
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        market_data = await self._get_json(f"/markets/{condition_id}")
        if not isinstance(market_data, dict):
            logger.warning("CLOB market not found or bad response", condition_id=condition_id)
            return None

        active: bool = bool(market_data.get("active", False))
        closed: bool = bool(market_data.get("closed", False))

        raw_volume = market_data.get("volume")
        raw_liquidity = market_data.get("liquidity")
        volume: Optional[float] = float(raw_volume) if raw_volume is not None else None
        liquidity: Optional[float] = float(raw_liquidity) if raw_liquidity is not None else None

        tokens: list[dict] = market_data.get("tokens", [])
        _yes_token_id = yes_token_id
        _no_token_id = no_token_id

        if not _yes_token_id or not _no_token_id:
            for tok in tokens:
                outcome = str(tok.get("outcome", "")).lower()
                tid = tok.get("token_id")
                if outcome in ("up", "yes") and not _yes_token_id:
                    _yes_token_id = tid
                elif outcome in ("down", "no") and not _no_token_id:
                    _no_token_id = tid

        yes_book = OrderBookSide(None, None)
        no_book = OrderBookSide(None, None)

        if _yes_token_id:
            yes_book = await self._fetch_order_book(_yes_token_id)
        if _no_token_id:
            no_book = await self._fetch_order_book(_no_token_id)

        yes_bid = yes_book.best_bid
        yes_ask = yes_book.best_ask
        no_bid = no_book.best_bid
        no_ask = no_book.best_ask

        yes_mid: Optional[float] = None
        if yes_bid is not None and yes_ask is not None:
            yes_mid = round((yes_bid + yes_ask) / 2, 6)
        elif yes_bid is not None:
            yes_mid = yes_bid
        elif yes_ask is not None:
            yes_mid = yes_ask
        else:
            for tok in tokens:
                outcome = str(tok.get("outcome", "")).lower()
                if outcome in ("up", "yes"):
                    try:
                        yes_mid = float(tok["price"])
                    except (KeyError, ValueError, TypeError):
                        pass
                    break

        no_mid: Optional[float] = None
        if no_bid is not None and no_ask is not None:
            no_mid = round((no_bid + no_ask) / 2, 6)
        elif no_bid is not None:
            no_mid = no_bid
        elif no_ask is not None:
            no_mid = no_ask
        else:
            for tok in tokens:
                outcome = str(tok.get("outcome", "")).lower()
                if outcome in ("down", "no"):
                    try:
                        no_mid = float(tok["price"])
                    except (KeyError, ValueError, TypeError):
                        pass
                    break

        spread_yes: Optional[float] = None
        if yes_bid is not None and yes_ask is not None:
            spread_yes = round(yes_ask - yes_bid, 6)

        spread_no: Optional[float] = None
        if no_bid is not None and no_ask is not None:
            spread_no = round(no_ask - no_bid, 6)

        logger.info(
            "CLOB market fetched",
            condition_id=condition_id[:12],
            yes_mid=yes_mid,
            no_mid=no_mid,
            spread_yes=spread_yes,
            active=active,
        )

        return ClobMarketData(
            condition_id=condition_id,
            yes_token_id=_yes_token_id,
            no_token_id=_no_token_id,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            yes_mid=yes_mid,
            no_bid=no_bid,
            no_ask=no_ask,
            no_mid=no_mid,
            spread_yes=spread_yes,
            spread_no=spread_no,
            volume=volume,
            liquidity=liquidity,
            active=active,
            closed=closed,
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> "ClobClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
