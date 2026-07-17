"""
Gamma Series API client — Sprint 7 / Sprint 8.6 fix / Phase 9D.

Fetches series metadata, events, and markets from the Polymarket
Gamma API (https://gamma-api.polymarket.com).

Responsibilities:
  - Fetch series info by slug           → GET /series?slug=
  - Fetch live/upcoming events          → GET /events?series_slug=
  - Fetch market resolution             → GET /markets?condition_ids=
  - Parse clobTokenIds (JSON string)    → YES token at [0], NO token at [1]
  - Retry logic with exponential backoff
  - Rate limiting between requests

Sprint 8.5 fix (Bug 2):
  Token IDs are now parsed from the clobTokenIds JSON string field
  (index 0 = YES, index 1 = NO) instead of a non-existent tokens[] array.

Sprint 8.6 fix (Bug 3):
  fetch_events now calls:
    GET /events?series_slug={slug}&order=startDate&ascending=false
  instead of GET /series?slug= which embeds events with empty markets[].

  The /series endpoint pre-stages upcoming events before they are
  deployed; their markets[] array is empty until deployment.
  The /events endpoint returns only deployed events whose markets are
  live on the CLOB with clobTokenIds populated.

  Ordering by startDate descending gives the 20 most-recently deployed
  events. After fetch, we sort by end_time ascending so the soonest-
  expiring market is identified as the active one.

Phase 9D — Direct Resolution:
  fetch_market_resolution calls GET /markets?condition_ids={id}.
  A market is CONFIRMED_RESOLVED only when:
    - closed == True (Polymarket has finalised the market)
    - outcomePrices has exactly two entries
    - One price rounds to 1 and the other rounds to 0 (≥ 0.99 threshold)
  Any other state (live probabilities, voided ["0","0"], missing data)
  returns outcome_source = NOT_AVAILABLE.  No winning_side is ever
  inferred from live probability data.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.http_client import classify_httpx_error, create_verified_httpx_client

logger = get_logger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = 20.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RATE_LIMIT_DELAY = 0.15

# Phase 9D: a price must be this close to 1.0 to be treated as a final outcome
RESOLUTION_THRESHOLD = 0.99

# Phase 9D: outcome_source labels
OUTCOME_SOURCE_DIRECT = "DIRECT_POLYMARKET_RESOLUTION"
OUTCOME_SOURCE_PROXY  = "REALIZED_PNL_PROXY"
OUTCOME_SOURCE_NONE   = "NOT_AVAILABLE"


# ── Phase 9D: Resolution result ────────────────────────────────────────────────

@dataclass
class MarketResolutionResult:
    """
    Result of a direct Polymarket/Gamma resolution lookup.

    outcome_source values:
      DIRECT_POLYMARKET_RESOLUTION — market is confirmed closed, winning_side
        is proven from provider data (outcomePrices clearly 1/0 or 0/1).
      NOT_AVAILABLE — market is not yet resolved, data is ambiguous, or the
        provider did not return sufficient evidence.  winning_side is None.

    winning_side: "YES" | "NO" | None
      Only set when outcome_source == DIRECT_POLYMARKET_RESOLUTION.

    final_yes_price / final_no_price:
      The raw outcomePrices[0] / [1] strings parsed as floats.  Present when
      the market was closed.  None otherwise.

    resolution_note: human-readable classification reason.
    """
    outcome_source: str          # DIRECT_POLYMARKET_RESOLUTION | NOT_AVAILABLE
    winning_side: Optional[str]  # YES | NO | None
    winning_token_id: Optional[str]
    final_yes_price: Optional[float]
    final_no_price: Optional[float]
    resolution_note: str


# ── Pydantic shapes for Gamma API responses ────────────────────────────────────

class GammaMarketRaw(BaseModel):
    id: Optional[str] = None
    condition_id: Optional[str] = Field(None, alias="conditionId")
    question: str = ""
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    active: bool = False
    closed: bool = False
    clob_token_ids: Optional[str] = Field(None, alias="clobTokenIds")
    # Phase 9D: resolution data — present on closed markets
    outcome_prices: Optional[str] = Field(None, alias="outcomePrices")

    model_config = {"populate_by_name": True}


class GammaEventRaw(BaseModel):
    id: Optional[str] = None
    slug: Optional[str] = None
    title: str = ""
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    active: bool = False
    closed: bool = False
    markets: list[GammaMarketRaw] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class GammaSeriesRaw(BaseModel):
    id: Optional[str] = None
    slug: Optional[str] = None
    title: str = ""

    model_config = {"populate_by_name": True}


# ── Parsed data classes returned to callers ────────────────────────────────────

class GammaMarket(BaseModel):
    condition_id: str
    question: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    is_active: bool
    is_closed: bool


class GammaEvent(BaseModel):
    event_id: Optional[str]
    slug: Optional[str]
    title: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    is_active: bool
    is_closed: bool
    markets: list[GammaMarket]


class GammaSeries(BaseModel):
    series_id: Optional[str]
    slug: str
    title: str


# ── Helper functions ───────────────────────────────────────────────────────────

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _extract_clob_token_ids(
    clob_token_ids: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Parse the clobTokenIds JSON string from the Gamma API.

    Format: "[\"<yes_token_id>\", \"<no_token_id>\"]"
    Index 0 = YES token, index 1 = NO token.

    Returns (yes_token_id, no_token_id).  Either may be None if the
    string is absent, malformed, or has fewer than two entries.
    """
    if not clob_token_ids:
        return None, None
    try:
        ids = json.loads(clob_token_ids)
        yes_id = str(ids[0]) if len(ids) > 0 else None
        no_id = str(ids[1]) if len(ids) > 1 else None
        return yes_id, no_id
    except (json.JSONDecodeError, IndexError, TypeError, ValueError):
        return None, None


# ── Client class ───────────────────────────────────────────────────────────────

class GammaSeriesClient:
    """
    Async HTTP client for the Polymarket Gamma API.

    Usage:
        async with GammaSeriesClient() as client:
            events = await client.fetch_events("btc-up-or-down-5m")
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = create_verified_httpx_client(
                base_url=GAMMA_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def _get_with_retry(self, path: str, params: dict) -> list[dict]:
        """
        GET request with exponential-backoff retry.

        Errors are classified before logging:
          SSL_ERROR    — TLS certificate verification failure
          CONNECT_ERROR — TCP/DNS failure
          TIMEOUT      — request timed out
          HTTP_4XX     — server returned 4xx
          HTTP_5XX     — server returned 5xx
          EMPTY_RESPONSE — HTTP 200 but empty / unexpected body
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.get(path, params=params)
                response.raise_for_status()
                body = response.json()
                if isinstance(body, list):
                    if not body:
                        logger.debug(
                            "Gamma API returned empty list",
                            path=path,
                            error_class="EMPTY_RESPONSE",
                        )
                    return body
                if isinstance(body, dict):
                    return body.get("data", [body])
                return []
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                error_class = classify_httpx_error(exc)
                wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Gamma API request failed, retrying",
                    attempt=attempt,
                    path=path,
                    error_class=error_class,
                    error=str(exc),
                    wait_seconds=wait,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)

        error_class = classify_httpx_error(last_exc) if last_exc else "UNKNOWN"
        logger.error(
            "Gamma API request exhausted retries",
            path=path,
            error_class=error_class,
            error=str(last_exc),
            retries=MAX_RETRIES,
        )
        return []

    async def fetch_series(self, slug: str) -> Optional[GammaSeries]:
        """Fetch metadata for a single series by slug."""
        await asyncio.sleep(RATE_LIMIT_DELAY)
        rows = await self._get_with_retry("/series", params={"slug": slug})
        if not rows:
            return None
        try:
            raw = GammaSeriesRaw.model_validate(rows[0])
            return GammaSeries(
                series_id=str(raw.id) if raw.id else None,
                slug=raw.slug or slug,
                title=raw.title,
            )
        except Exception as exc:
            logger.warning("Failed to parse series", slug=slug, error=str(exc))
            return None

    async def fetch_events(
        self,
        series_slug: str,
        limit: int = 20,
    ) -> list[GammaEvent]:
        """
        Fetch active and upcoming events for the given series slug.

        Calls GET /events?series_slug={slug}&order=startDate&ascending=false
        which returns the most recently DEPLOYED events (limit up to 20).
        These have markets[] populated with conditionId and clobTokenIds.

        Important: the GET /series endpoint embeds events in series.events[]
        but those events are pre-staged and have empty markets[] until
        deployment.  Never use that array for live market data.

        The returned events are sorted by end_time ascending before being
        returned so callers can rely on index 0 being the active market.
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        rows = await self._get_with_retry(
            "/events",
            params={
                "series_slug": series_slug,
                "limit": limit,
                "order": "startDate",
                "ascending": "false",
            },
        )

        events: list[GammaEvent] = []
        for row in rows:
            try:
                raw = GammaEventRaw.model_validate(row)
                markets = self._parse_markets(raw.markets)
                if not markets:
                    continue
                events.append(
                    GammaEvent(
                        event_id=str(raw.id) if raw.id else None,
                        slug=raw.slug,
                        title=raw.title,
                        start_time=_parse_dt(raw.start_date),
                        end_time=_parse_dt(raw.end_date),
                        is_active=raw.active,
                        is_closed=raw.closed,
                        markets=markets,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to parse event",
                    series_slug=series_slug,
                    error=str(exc),
                )

        # Sort by end_time ascending: index 0 = soonest expiry = active market
        now = datetime.now(timezone.utc)
        events = [e for e in events if not e.is_closed and e.end_time and e.end_time > now]
        events.sort(key=lambda e: e.end_time)  # type: ignore[arg-type]

        logger.info(
            "Gamma events fetched",
            series_slug=series_slug,
            events_count=len(events),
        )
        return events

    async def fetch_event_by_slug(self, event_slug: str) -> Optional[GammaEvent]:
        """
        Fetch a single Gamma event by its exact event slug.

        Used for timestamp-slug primary discovery:
            GET /events?slug={asset}-updown-5m-{unix_slot}

        Returns the first matching event (there should be exactly one per slug),
        or None if not found or parsing fails.
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        rows = await self._get_with_retry("/events", params={"slug": event_slug})
        if not rows:
            logger.debug("fetch_event_by_slug: no result", event_slug=event_slug)
            return None
        try:
            raw = GammaEventRaw.model_validate(rows[0])
            markets = self._parse_markets(raw.markets)
            if not markets:
                logger.debug(
                    "fetch_event_by_slug: event has no markets",
                    event_slug=event_slug,
                )
                return None
            return GammaEvent(
                event_id=str(raw.id) if raw.id else None,
                slug=raw.slug,
                title=raw.title,
                start_time=_parse_dt(raw.start_date),
                end_time=_parse_dt(raw.end_date),
                is_active=raw.active,
                is_closed=raw.closed,
                markets=markets,
            )
        except Exception as exc:
            logger.warning(
                "fetch_event_by_slug: parse error",
                event_slug=event_slug,
                error=str(exc),
            )
            return None

    async def fetch_active_market(self, series_slug: str) -> Optional[GammaMarket]:
        """
        Return the single currently-active market for a series.

        The active market is at index 0 of fetch_events() (soonest
        future end_time, already sorted by the fetch).
        """
        events = await self.fetch_events(series_slug, limit=20)
        if events:
            for market in events[0].markets:
                if not market.is_closed:
                    return market
        return None

    async def fetch_next_markets(
        self, series_slug: str, count: int = 3
    ) -> list[GammaMarket]:
        """
        Return up to `count` upcoming markets after the current active one.

        Upcoming = events[1:] from fetch_events() (already sorted by
        end_time ascending, skipping the active market at index 0).
        """
        events = await self.fetch_events(series_slug, limit=20)
        upcoming_events = events[1:]  # skip the active (index 0)
        results: list[GammaMarket] = []
        for event in upcoming_events:
            results.extend(event.markets)
            if len(results) >= count:
                break
        return results[:count]

    def _parse_markets(self, raw_markets: list[GammaMarketRaw]) -> list[GammaMarket]:
        """Convert raw market dicts to typed GammaMarket objects."""
        parsed: list[GammaMarket] = []
        for raw in raw_markets:
            cid = raw.condition_id or raw.id
            if not cid:
                continue
            yes_id, no_id = _extract_clob_token_ids(raw.clob_token_ids)
            parsed.append(
                GammaMarket(
                    condition_id=cid,
                    question=raw.question,
                    yes_token_id=yes_id,
                    no_token_id=no_id,
                    start_time=_parse_dt(raw.start_date),
                    end_time=_parse_dt(raw.end_date),
                    is_active=raw.active,
                    is_closed=raw.closed,
                )
            )
        return parsed

    # ── Phase 9D: Direct Resolution ───────────────────────────────────────────

    async def fetch_market_resolution(
        self,
        condition_id: str,
        yes_token_id: Optional[str] = None,
        no_token_id: Optional[str] = None,
    ) -> MarketResolutionResult:
        """
        Query Polymarket/Gamma for direct market resolution evidence.

        Calls GET /markets?condition_ids={condition_id} and classifies:

        DIRECT_POLYMARKET_RESOLUTION:
          - market.closed == True
          - outcomePrices has exactly two entries
          - outcomePrices[0] >= RESOLUTION_THRESHOLD → YES wins
          - outcomePrices[1] >= RESOLUTION_THRESHOLD → NO wins
          (index 0 = YES token, index 1 = NO token, same as clobTokenIds)

        NOT_AVAILABLE (never infer a winner):
          - market is not closed (still live — outcomePrices are live probabilities)
          - outcomePrices is missing or malformed
          - outcomePrices is voided ["0","0"] or ["0.5","0.5"]
          - API returned no matching market

        The condition_id must match exactly — no fuzzy lookup.
        yes_token_id / no_token_id are used to set winning_token_id on the
        returned result when a winner is confirmed.

        Returns:
            MarketResolutionResult
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        rows = await self._get_with_retry(
            "/markets",
            params={"condition_ids": condition_id, "closed": "true"},
        )

        if not rows:
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=None,
                final_no_price=None,
                resolution_note="No market data returned from Gamma API",
            )

        # Find the row whose conditionId matches exactly
        matched: Optional[dict] = None
        for row in rows:
            raw_cid = row.get("conditionId", "")
            if str(raw_cid).lower() == condition_id.lower():
                matched = row
                break

        if matched is None:
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=None,
                final_no_price=None,
                resolution_note=f"condition_id not found in API response (got {len(rows)} rows)",
            )

        try:
            raw = GammaMarketRaw.model_validate(matched)
        except Exception as exc:
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=None,
                final_no_price=None,
                resolution_note=f"Failed to parse market row: {exc}",
            )

        # Market must be closed — otherwise outcomePrices are live probabilities
        if not raw.closed:
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=None,
                final_no_price=None,
                resolution_note="Market not yet closed — outcomePrices are live probabilities, not resolution",
            )

        # Parse outcomePrices — expected as JSON string e.g. '["1","0"]'
        yes_price, no_price = self._parse_outcome_prices(raw.outcome_prices)

        if yes_price is None or no_price is None:
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=yes_price,
                final_no_price=no_price,
                resolution_note="Closed market but outcomePrices missing or malformed",
            )

        # Classify winning side — both sides must be unambiguous
        if yes_price >= RESOLUTION_THRESHOLD and no_price <= (1.0 - RESOLUTION_THRESHOLD):
            winning_side = "YES"
            winning_token = yes_token_id
        elif no_price >= RESOLUTION_THRESHOLD and yes_price <= (1.0 - RESOLUTION_THRESHOLD):
            winning_side = "NO"
            winning_token = no_token_id
        else:
            # Voided ["0","0"], ambiguous, or partially settled
            return MarketResolutionResult(
                outcome_source=OUTCOME_SOURCE_NONE,
                winning_side=None,
                winning_token_id=None,
                final_yes_price=yes_price,
                final_no_price=no_price,
                resolution_note=(
                    f"Closed market but outcomePrices [{yes_price},{no_price}] "
                    f"do not meet resolution threshold {RESOLUTION_THRESHOLD} — "
                    "voided or ambiguous outcome"
                ),
            )

        logger.info(
            "[Phase 9D] Direct resolution confirmed",
            condition_id=condition_id[:16],
            winning_side=winning_side,
            yes_price=yes_price,
            no_price=no_price,
        )

        return MarketResolutionResult(
            outcome_source=OUTCOME_SOURCE_DIRECT,
            winning_side=winning_side,
            winning_token_id=winning_token,
            final_yes_price=yes_price,
            final_no_price=no_price,
            resolution_note=(
                f"DIRECT_RESOLUTION_CONFIRMED: market closed, "
                f"outcomePrices=[{yes_price},{no_price}], winner={winning_side}"
            ),
        )

    @staticmethod
    def _parse_outcome_prices(
        outcome_prices: Optional[str],
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Parse the outcomePrices field from the Gamma API.

        The field is a JSON string: '["1","0"]' or '["0.505","0.495"]'.
        Index 0 = YES token price, index 1 = NO token price.

        Returns (yes_price, no_price) as floats.  Either may be None if
        parsing fails or the list has fewer than two entries.
        """
        if not outcome_prices:
            return None, None
        try:
            prices = json.loads(outcome_prices)
            yes_p = float(prices[0]) if len(prices) > 0 else None
            no_p  = float(prices[1]) if len(prices) > 1 else None
            return yes_p, no_p
        except (json.JSONDecodeError, IndexError, TypeError, ValueError):
            return None, None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> "GammaSeriesClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
