"""
Source Validator — Sprint 5.

Answers: "Can we reliably discover the exact market family that the user wants?"

Target family:
    BTC / ETH / SOL / XRP  ×  Up or Down  ×  5m / 15m / 1H

This module:
  1. Fetches raw markets from the Polymarket CLOB endpoint.
  2. Records the full source lineage for every asset-matched market.
  3. Applies the Exact Matcher to flag Up/Down candidates.
  4. Persists results to ``source_validation_results``.

Exact Matcher patterns (Task 4):
    up, down, up/down, higher, lower, above, below,
    5 minutes, 15 minutes, 1 hour
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.services.market_discovery import (
    ASSET_RULES,
    TIMEFRAME_RULES,
    _match_asset,
    _match_timeframe,
)

logger = get_logger(__name__)

CLOB_BASE_URL = "https://clob.polymarket.com"
SOURCE_ENDPOINT = f"{CLOB_BASE_URL}/markets"
REQUEST_TIMEOUT = 15.0
PAGE_SIZE = 100
MAX_PAGES = 250


# ── Exact Matcher patterns (Task 4) ───────────────────────────────────────────

_EXACT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("up",           re.compile(r"\bup\b",             re.IGNORECASE)),
    ("down",         re.compile(r"\bdown\b",           re.IGNORECASE)),
    ("up_down",      re.compile(r"\bup/down\b",        re.IGNORECASE)),
    ("higher",       re.compile(r"\bhigher\b",         re.IGNORECASE)),
    ("lower",        re.compile(r"\blower\b",          re.IGNORECASE)),
    ("above",        re.compile(r"\babove\b",          re.IGNORECASE)),
    ("below",        re.compile(r"\bbelow\b",          re.IGNORECASE)),
    ("5_minutes",    re.compile(r"\b5\s+minutes?\b",   re.IGNORECASE)),
    ("15_minutes",   re.compile(r"\b15\s+minutes?\b",  re.IGNORECASE)),
    ("1_hour",       re.compile(r"\b1\s+hour\b",       re.IGNORECASE)),
]


def match_exact_patterns(title: str) -> list[str]:
    """Return list of matched keyword names from the exact matcher pattern set."""
    return [name for name, pat in _EXACT_PATTERNS if pat.search(title)]


def is_updown_candidate(title: str) -> tuple[bool, str]:
    """
    Return (is_candidate, comma-separated keywords found).

    A market is an Up/Down candidate if at least one exact pattern fires.
    """
    found = match_exact_patterns(title)
    return bool(found), ", ".join(found)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ValidatedMarket:
    """A single market with full source tracing and detection results."""

    source_endpoint: str
    source_market_id: str
    condition_id: str
    title: str
    slug: Optional[str]
    source_event_id: Optional[str]
    detected_asset: Optional[str]
    detected_timeframe: Optional[str]
    is_updown_candidate: bool
    updown_keywords_found: str
    matching_rule: Optional[str]


@dataclass
class ValidationRun:
    """Aggregated result of one full validation scan."""

    run_id: str
    run_at: datetime
    source: str
    total_scanned: int
    total_asset_matched: int
    total_updown_candidates: int
    markets: list[ValidatedMarket] = field(default_factory=list)

    # Per-asset candidate counts
    btc_candidates: int = 0
    eth_candidates: int = 0
    sol_candidates: int = 0
    xrp_candidates: int = 0

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_at": self.run_at.isoformat(),
            "source": self.source,
            "total_scanned": self.total_scanned,
            "total_asset_matched": self.total_asset_matched,
            "total_updown_candidates": self.total_updown_candidates,
            "btc_candidates": self.btc_candidates,
            "eth_candidates": self.eth_candidates,
            "sol_candidates": self.sol_candidates,
            "xrp_candidates": self.xrp_candidates,
        }


# ── Validator service ──────────────────────────────────────────────────────────

class SourceValidatorService:
    """
    Scans the Polymarket CLOB, applies exact matching, and stores
    source tracing data for every asset-matched market.

    Usage:
        svc = SourceValidatorService()
        run = await svc.validate()
        await svc.close()
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
        client = await self._get_client()
        params: dict = {"limit": PAGE_SIZE, "active": "true"}
        if next_cursor:
            params["next_cursor"] = next_cursor

        response = await client.get("/markets", params=params)
        response.raise_for_status()
        body = response.json()

        if isinstance(body, dict):
            return body.get("data", []), body.get("next_cursor", "")
        return body, ""

    def _process_raw_market(self, raw: dict) -> Optional[ValidatedMarket]:
        """
        Extract and validate a single raw CLOB market record.

        Returns None if the market lacks required fields or has no asset match.
        """
        title: str = raw.get("question", "") or raw.get("title", "")
        condition_id: str = raw.get("condition_id", "")
        if not title or not condition_id:
            return None

        # Asset filter — only BTC / ETH / SOL / XRP
        asset_match = _match_asset(title)
        if not asset_match:
            return None

        asset_rule, asset = asset_match

        # Timeframe detection (optional — not a hard filter here)
        tf_match = _match_timeframe(title)
        detected_tf: Optional[str] = None
        tf_rule: Optional[str] = None
        if tf_match:
            tf_rule_name, _, detected_tf = tf_match
            tf_rule = tf_rule_name

        matching_rule = f"{asset_rule}" + (f" + {tf_rule}" if tf_rule else "")

        candidate, keywords = is_updown_candidate(title)

        return ValidatedMarket(
            source_endpoint=SOURCE_ENDPOINT,
            source_market_id=condition_id,
            condition_id=condition_id,
            title=title,
            slug=raw.get("market_slug") or raw.get("slug") or None,
            source_event_id=str(raw["event_id"]) if raw.get("event_id") else None,
            detected_asset=asset,
            detected_timeframe=detected_tf,
            is_updown_candidate=candidate,
            updown_keywords_found=keywords,
            matching_rule=matching_rule,
        )

    async def validate(self) -> ValidationRun:
        """
        Paginate all active Polymarket markets, apply the exact matcher,
        and return a ValidationRun with per-market results.

        Callers should persist the run via ``save_validation_run()``.
        """
        run_id = str(uuid.uuid4())
        run_at = datetime.now(timezone.utc)
        markets: list[ValidatedMarket] = []
        total_scanned = 0
        asset_counts: dict[str, int] = {"BTC": 0, "ETH": 0, "SOL": 0, "XRP": 0}

        next_cursor = ""
        pages = 0

        logger.info("Source validation started", run_id=run_id)

        while pages < MAX_PAGES:
            try:
                raw_list, next_cursor = await self._fetch_page(next_cursor)
            except Exception as exc:
                logger.error(
                    "Source validation page fetch failed",
                    page=pages,
                    run_id=run_id,
                    error=str(exc),
                )
                break

            pages += 1
            total_scanned += len(raw_list)

            for raw in raw_list:
                vm = self._process_raw_market(raw)
                if vm is None:
                    continue
                markets.append(vm)
                if vm.detected_asset in asset_counts:
                    asset_counts[vm.detected_asset] += 1

            logger.debug(
                "Source validation page done",
                page=pages,
                scanned=total_scanned,
                asset_matched=len(markets),
            )

            if not next_cursor or next_cursor in ("LTE=", ""):
                break

        candidates = [m for m in markets if m.is_updown_candidate]

        run = ValidationRun(
            run_id=run_id,
            run_at=run_at,
            source="clob",
            total_scanned=total_scanned,
            total_asset_matched=len(markets),
            total_updown_candidates=len(candidates),
            markets=markets,
            btc_candidates=sum(1 for m in candidates if m.detected_asset == "BTC"),
            eth_candidates=sum(1 for m in candidates if m.detected_asset == "ETH"),
            sol_candidates=sum(1 for m in candidates if m.detected_asset == "SOL"),
            xrp_candidates=sum(1 for m in candidates if m.detected_asset == "XRP"),
        )

        logger.info(
            "Source validation complete",
            run_id=run_id,
            total_scanned=total_scanned,
            asset_matched=len(markets),
            updown_candidates=len(candidates),
            pages=pages,
        )
        return run

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None


# ── Repository helpers ────────────────────────────────────────────────────────

async def save_validation_run(session, run: ValidationRun) -> None:
    """Persist all markets from a ValidationRun into source_validation_results."""
    from app.models.source_validation_result import SourceValidationResult

    now = run.run_at
    for vm in run.markets:
        row = SourceValidationResult(
            run_id=run.run_id,
            created_at=now,
            source_endpoint=vm.source_endpoint,
            source_event_id=vm.source_event_id,
            source_market_id=vm.source_market_id,
            condition_id=vm.condition_id,
            title=vm.title,
            slug=vm.slug,
            detected_asset=vm.detected_asset,
            detected_timeframe=vm.detected_timeframe,
            is_updown_candidate=vm.is_updown_candidate,
            updown_keywords_found=vm.updown_keywords_found or None,
            matching_rule=vm.matching_rule,
        )
        session.add(row)
    await session.flush()


async def get_total_stored(session) -> int:
    """Return the total number of source_validation_results rows."""
    from sqlalchemy import func, select
    from app.models.source_validation_result import SourceValidationResult

    result = await session.execute(
        select(func.count()).select_from(SourceValidationResult)
    )
    return result.scalar_one()


async def search_results(session, q: str, limit: int = 100) -> list:
    """Full-text search across title and slug columns."""
    from sqlalchemy import or_, select
    from app.models.source_validation_result import SourceValidationResult

    pattern = f"%{q}%"
    stmt = (
        select(SourceValidationResult)
        .where(
            or_(
                SourceValidationResult.title.ilike(pattern),
                SourceValidationResult.slug.ilike(pattern),
            )
        )
        .order_by(SourceValidationResult.created_at.desc())
        .limit(limit)
    )
    rows = await session.execute(stmt)
    return rows.scalars().all()


async def get_audit_results(session, limit: int = 1000) -> list:
    """Return all Up/Down candidate markets, most recent run first."""
    from sqlalchemy import select
    from app.models.source_validation_result import SourceValidationResult

    stmt = (
        select(SourceValidationResult)
        .where(SourceValidationResult.is_updown_candidate.is_(True))
        .order_by(SourceValidationResult.created_at.desc())
        .limit(limit)
    )
    rows = await session.execute(stmt)
    return rows.scalars().all()
