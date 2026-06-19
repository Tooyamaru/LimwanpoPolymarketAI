"""
Gamma Series API client — Sprint 7 / Sprint 8.5 fix.

Fetches series metadata, events, and markets from the Polymarket
Gamma API (https://gamma-api.polymarket.com).

Responsibilities:
  - Fetch series info by slug
  - Fetch active and upcoming events for a series via GET /series?slug=
  - Parse clobTokenIds (JSON string) for YES / NO token IDs
  - Retry logic with exponential backoff
  - Rate limiting between requests

Sprint 8.5 fixes:
  Bug 1 — fetch_events now calls GET /series?slug= (returns embedded
           live events) instead of GET /events?series_slug= (returned
           historical events only).
  Bug 2 — token IDs are parsed from the clobTokenIds JSON string field
           (index 0 = YES, index 1 = NO) instead of a non-existent
           tokens[] array.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = 20.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RATE_LIMIT_DELAY = 0.15


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
    events: list[GammaEventRaw] = Field(default_factory=list)

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
            self._client = httpx.AsyncClient(
                base_url=GAMMA_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def _get_with_retry(self, path: str, params: dict) -> list[dict]:
        """GET request with exponential-backoff retry."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.get(path, params=params)
                response.raise_for_status()
                body = response.json()
                if isinstance(body, list):
                    return body
                if isinstance(body, dict):
                    return body.get("data", [body])
                return []
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Gamma API request failed, retrying",
                    attempt=attempt,
                    path=path,
                    error=str(exc),
                    wait_seconds=wait,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)

        logger.error("Gamma API request exhausted retries", path=path, error=str(last_exc))
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

        Calls GET /series?slug={series_slug} which returns the series
        object with its currently live events embedded in events[].
        This is the authoritative source used by the Polymarket website.

        Sprint 8.5: replaces the old GET /events?series_slug= call that
        returned historical (expired) events only.
        """
        await asyncio.sleep(RATE_LIMIT_DELAY)
        rows = await self._get_with_retry(
            "/series",
            params={"slug": series_slug},
        )

        if not rows:
            logger.info(
                "Gamma events fetched",
                series_slug=series_slug,
                events_count=0,
            )
            return []

        series_data = rows[0] if isinstance(rows[0], dict) else {}
        event_rows: list[dict] = series_data.get("events", [])

        events: list[GammaEvent] = []
        for row in event_rows:
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

        logger.info(
            "Gamma events fetched",
            series_slug=series_slug,
            events_count=len(events),
        )
        return events

    async def fetch_active_market(self, series_slug: str) -> Optional[GammaMarket]:
        """
        Return the single currently-active market for a series.

        The active market is the one with the soonest future end_time
        among all open (not closed) events in the series.
        """
        now = datetime.now(timezone.utc)
        events = await self.fetch_events(series_slug, limit=20)
        open_events = [
            e for e in events
            if not e.is_closed and e.end_time and e.end_time > now
        ]
        open_events.sort(key=lambda e: e.end_time)  # type: ignore[arg-type]
        if open_events:
            for market in open_events[0].markets:
                if not market.is_closed:
                    return market
        return None

    async def fetch_next_markets(
        self, series_slug: str, count: int = 3
    ) -> list[GammaMarket]:
        """
        Return up to `count` upcoming markets after the current active one.

        Upcoming = all open events sorted by end_time, skipping the first
        (the active one).
        """
        now = datetime.now(timezone.utc)
        events = await self.fetch_events(series_slug, limit=20)
        open_events = [
            e for e in events
            if not e.is_closed and e.end_time and e.end_time > now
        ]
        open_events.sort(key=lambda e: e.end_time)  # type: ignore[arg-type]
        upcoming_events = open_events[1:]  # skip the active (first) event
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

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> "GammaSeriesClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
