"""
Market Discovery Engine — Sprint 3 / Sprint 4.

Scans ALL active Polymarket markets, counts totals, and identifies which
markets match our tracked asset + timeframe universe.

Sprint 4 addition: runs EventClassifier on EVERY scanned market to accumulate
aggregate classification statistics (UPDOWN / PRICE_RANGE / NEWS_EVENT /
POLITICS / OTHER) across the full 250k+ market corpus.

Transparency fields stored per matched market:
  raw_title           — exact question string from Polymarket
  matching_rule       — asset+timeframe rule that triggered the match
  detected_asset      — normalised asset (BTC / ETH / SOL / XRP)
  detected_timeframe  — normalised timeframe (5m / 15m / 1H)
  event_type          — EventClassifier output (UPDOWN etc.)
  confidence          — classifier confidence score
  classification_rule — classifier rule name that fired
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.services.event_classifier import EventClassifier, EventType

logger = get_logger(__name__)

CLOB_BASE_URL = "https://clob.polymarket.com"
REQUEST_TIMEOUT = 15.0
PAGE_SIZE = 100
MAX_PAGES = 250   # 250 pages; Polymarket returns ~1000 records/page → ~250k markets

# ── Asset match rules ─────────────────────────────────────────────────────────

ASSET_RULES: list[tuple[str, str]] = [
    ("exact_BTC",    r"\bBTC\b"),
    ("exact_ETH",    r"\bETH\b"),
    ("exact_SOL",    r"\bSOL\b"),
    ("exact_XRP",    r"\bXRP\b"),
    ("word_Bitcoin", r"\bBitcoin\b"),
    ("word_Ethereum",r"\bEthereum\b"),
    ("word_Solana",  r"\bSolana\b"),
    ("word_Ripple",  r"\bRipple\b"),
]

ASSET_NORMALISE: dict[str, str] = {
    "BTC": "BTC", "Bitcoin": "BTC",
    "ETH": "ETH", "Ethereum": "ETH",
    "SOL": "SOL", "Solana": "SOL",
    "XRP": "XRP", "Ripple": "XRP",
}

TIMEFRAME_RULES: list[tuple[str, str, str]] = [
    ("tf_5m",       r"\b5\s*m(?:in(?:ute)?s?)?\b",   "5m"),
    ("tf_15m",      r"\b15\s*m(?:in(?:ute)?s?)?\b",  "15m"),
    ("tf_1H_abbr",  r"\b1\s*[Hh]\b",                 "1H"),
    ("tf_1H_word",  r"\b1[\s-]?hour\b",               "1H"),
    ("tf_60m",      r"\b60\s*m(?:in(?:ute)?s?)?\b",   "1H"),
]


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class MatchedMarket:
    market_id: str
    title: str
    asset: str
    timeframe: str
    raw_title: str
    matching_rule: str          # asset+timeframe rule, e.g. "exact_BTC + tf_5m"
    detected_asset: str
    detected_timeframe: str
    yes_price: float = 0.0
    no_price: float = 0.0
    liquidity: float = 0.0
    volume: float = 0.0
    end_time: Optional[datetime] = None

    # ── Sprint 4 classifier fields ────────────────────────────────────────────
    event_type: str = EventType.OTHER.value
    confidence: float = 0.0
    classification_rule: str = ""


@dataclass
class DiscoveryResult:
    run_at: datetime
    total_scanned: int
    total_matched: int
    matched_markets: list[MatchedMarket] = field(default_factory=list)

    # Per-asset counts (asset+timeframe matched markets)
    btc_count: int = 0
    eth_count: int = 0
    sol_count: int = 0
    xrp_count: int = 0

    # Sprint 4: classification counts across ALL scanned markets
    updown_count: int = 0
    price_range_count: int = 0
    news_event_count: int = 0
    politics_count: int = 0
    other_count: int = 0

    def as_dict(self) -> dict:
        return {
            "run_at": self.run_at.isoformat(),
            "total_markets_scanned": self.total_scanned,
            "matched_markets": self.total_matched,
            "btc": self.btc_count,
            "eth": self.eth_count,
            "sol": self.sol_count,
            "xrp": self.xrp_count,
            "classification": {
                "updown": self.updown_count,
                "price_range": self.price_range_count,
                "news_event": self.news_event_count,
                "politics": self.politics_count,
                "other": self.other_count,
            },
        }


# ── Matching helpers ──────────────────────────────────────────────────────────

def _match_asset(title: str) -> Optional[tuple[str, str]]:
    for rule_name, pattern in ASSET_RULES:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            keyword = m.group(0).strip()
            for key, asset in ASSET_NORMALISE.items():
                if keyword.upper() == key.upper() or keyword.lower() == key.lower():
                    return rule_name, asset
            asset = rule_name.split("_")[-1].upper()
            return rule_name, asset
    return None


def _match_timeframe(title: str) -> Optional[tuple[str, str, str]]:
    for rule_name, pattern, normalised in TIMEFRAME_RULES:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            return rule_name, m.group(0).strip(), normalised
    return None


def _parse_token_price(tokens: list[dict], outcome: str) -> float:
    for token in tokens:
        if token.get("outcome", "").upper() == outcome.upper():
            try:
                return float(token.get("price", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


# ── Discovery engine ──────────────────────────────────────────────────────────

class MarketDiscoveryService:
    """
    Scans all active Polymarket markets and returns a DiscoveryResult.

    Sprint 4: runs EventClassifier on EVERY market to accumulate
    classification stats across the full corpus.  Only asset+timeframe
    matched markets are stored in matched_markets, but all classification
    counts reflect the entire scan.
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

    async def discover(self) -> DiscoveryResult:
        """
        Paginate all active Polymarket markets.

        For every market:
          1. Run EventClassifier (accumulate global classification stats).
          2. Check asset + timeframe filter.
          3. If both match, add to matched_markets with full transparency.
        """
        run_at = datetime.now(timezone.utc)
        total_scanned = 0
        matched: list[MatchedMarket] = []
        asset_counts: dict[str, int] = {"BTC": 0, "ETH": 0, "SOL": 0, "XRP": 0}

        # Sprint 4: global classification counters (all markets)
        class_counts: dict[str, int] = {et.value: 0 for et in EventType}

        next_cursor = ""
        pages = 0

        logger.info("Market discovery started")

        while pages < MAX_PAGES:
            try:
                raw_list, next_cursor = await self._fetch_page(next_cursor)
            except Exception as exc:
                logger.error("Discovery page fetch failed", page=pages, error=str(exc))
                break

            pages += 1
            total_scanned += len(raw_list)

            for raw in raw_list:
                title: str = raw.get("question", "") or raw.get("title", "")
                condition_id: str = raw.get("condition_id", "")
                if not title or not condition_id:
                    continue

                # ── Sprint 4: classify EVERY market for global stats ──────────
                clf = EventClassifier.classify(title)
                class_counts[clf.event_type.value] += 1

                # ── Asset + timeframe filter ──────────────────────────────────
                asset_match = _match_asset(title)
                if not asset_match:
                    continue
                asset_rule, asset = asset_match

                tf_match = _match_timeframe(title)
                if not tf_match:
                    continue
                tf_rule, tf_raw, timeframe = tf_match

                # Re-classify with asset+timeframe context for higher confidence
                clf_ctx = EventClassifier.classify(title, asset=asset, timeframe=tf_raw)

                combined_rule = f"{asset_rule} + {tf_rule}"

                tokens: list[dict] = raw.get("tokens", []) or []
                yes_price = _parse_token_price(tokens, "Yes")
                no_price = _parse_token_price(tokens, "No")
                if yes_price == 0.0 and no_price == 0.0:
                    no_price = round(1.0 - yes_price, 4)

                end_time: Optional[datetime] = None
                end_str = raw.get("end_date_iso")
                if end_str:
                    try:
                        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                mm = MatchedMarket(
                    market_id=condition_id,
                    title=title,
                    asset=asset,
                    timeframe=timeframe,
                    raw_title=title,
                    matching_rule=combined_rule,
                    detected_asset=asset,
                    detected_timeframe=tf_raw,
                    yes_price=yes_price,
                    no_price=no_price,
                    liquidity=float(raw.get("liquidity", 0) or 0),
                    volume=float(raw.get("volume", 0) or 0),
                    end_time=end_time,
                    event_type=clf_ctx.event_type.value,
                    confidence=clf_ctx.confidence,
                    classification_rule=clf_ctx.matched_rule,
                )
                matched.append(mm)

                if asset in asset_counts:
                    asset_counts[asset] += 1

            logger.debug(
                "Discovery page complete",
                page=pages,
                total_scanned=total_scanned,
                matched_so_far=len(matched),
            )

            if not next_cursor or next_cursor in ("LTE=", ""):
                break

        result = DiscoveryResult(
            run_at=run_at,
            total_scanned=total_scanned,
            total_matched=len(matched),
            matched_markets=matched,
            btc_count=asset_counts["BTC"],
            eth_count=asset_counts["ETH"],
            sol_count=asset_counts["SOL"],
            xrp_count=asset_counts["XRP"],
            updown_count=class_counts[EventType.UPDOWN.value],
            price_range_count=class_counts[EventType.PRICE_RANGE.value],
            news_event_count=class_counts[EventType.NEWS_EVENT.value],
            politics_count=class_counts[EventType.POLITICS.value],
            other_count=class_counts[EventType.OTHER.value],
        )

        logger.info(
            "Market discovery complete",
            total_scanned=total_scanned,
            matched=len(matched),
            pages=pages,
            updown=result.updown_count,
            price_range=result.price_range_count,
            news_event=result.news_event_count,
            politics=result.politics_count,
            other=result.other_count,
            **{k.lower(): v for k, v in asset_counts.items()},
        )
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
