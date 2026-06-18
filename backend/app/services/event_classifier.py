"""
Event Classifier — Sprint 4.

Classifies any Polymarket market title into one of:
    UPDOWN      — "BTC Up or Down in 5m" style markets (highest priority)
    PRICE_RANGE — price level / threshold markets
    NEWS_EVENT  — crypto news / tech-event markets
    POLITICS    — political / electoral markets
    OTHER       — everything else

Classification is purely in-memory (no DB) and runs on EVERY scanned market so
the discovery engine can accumulate aggregate statistics across all 250k+ markets.

Priority order: UPDOWN > PRICE_RANGE > NEWS_EVENT > POLITICS > OTHER

Transparency: every Classification carries the rule name and confidence score so
callers can audit why a market was classified a specific way.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    UPDOWN = "UPDOWN"
    PRICE_RANGE = "PRICE_RANGE"
    NEWS_EVENT = "NEWS_EVENT"
    POLITICS = "POLITICS"
    OTHER = "OTHER"


@dataclass
class Classification:
    event_type: EventType
    confidence: float       # 0.0 – 1.0
    matched_rule: str       # human-readable rule that fired


# ── Rule tables ───────────────────────────────────────────────────────────────
# Each entry: (rule_name, compiled_pattern)

_UPDOWN_RULES: list[tuple[str, re.Pattern]] = [
    ("updown_phrase",    re.compile(r"\bup\s+or\s+down\b",   re.IGNORECASE)),
    ("downup_phrase",    re.compile(r"\bdown\s+or\s+up\b",   re.IGNORECASE)),
    ("updown_slash",     re.compile(r"\bup/down\b",          re.IGNORECASE)),
    ("updown_hyphen",    re.compile(r"\bup-or-down\b",       re.IGNORECASE)),
    ("updown_compound",  re.compile(r"\bupdown\b",           re.IGNORECASE)),
]

_PRICE_RANGE_RULES: list[tuple[str, re.Pattern]] = [
    ("above_price",    re.compile(r"\babove\b",              re.IGNORECASE)),
    ("below_price",    re.compile(r"\bbelow\b",              re.IGNORECASE)),
    ("over_price",     re.compile(r"\bover\b",               re.IGNORECASE)),
    ("under_price",    re.compile(r"\bunder\b",              re.IGNORECASE)),
    ("between_range",  re.compile(r"\bbetween\b",            re.IGNORECASE)),
    ("dollar_amount",  re.compile(r"\$[\d,]+",               re.IGNORECASE)),
    ("gt_price",       re.compile(r">\s*\$?[\d,]+",         re.IGNORECASE)),
    ("lt_price",       re.compile(r"<\s*\$?[\d,]+",         re.IGNORECASE)),
    ("hit_level",      re.compile(r"\bhit\b",                re.IGNORECASE)),
    ("reach_level",    re.compile(r"\breach\b",              re.IGNORECASE)),
    ("exceed_level",   re.compile(r"\bexceed\b",             re.IGNORECASE)),
    ("break_level",    re.compile(r"\bbreak\b",              re.IGNORECASE)),
]

_NEWS_EVENT_RULES: list[tuple[str, re.Pattern]] = [
    ("etf_event",      re.compile(r"\betf\b",                re.IGNORECASE)),
    ("halving_event",  re.compile(r"\bhalving\b",            re.IGNORECASE)),
    ("fork_event",     re.compile(r"\bfork\b",               re.IGNORECASE)),
    ("sec_event",      re.compile(r"\bsec\b",                re.IGNORECASE)),
    ("regulation",     re.compile(r"\bregulat\w*\b",         re.IGNORECASE)),
    ("hack_event",     re.compile(r"\bhack\w*\b",            re.IGNORECASE)),
    ("launch_event",   re.compile(r"\blaunch\b",             re.IGNORECASE)),
    ("upgrade_event",  re.compile(r"\bupgrade\b",            re.IGNORECASE)),
    ("mainnet_event",  re.compile(r"\bmainnet\b",            re.IGNORECASE)),
    ("airdrop_event",  re.compile(r"\bairdrop\b",            re.IGNORECASE)),
    ("approval_event", re.compile(r"\bapproval\b",           re.IGNORECASE)),
    ("listing_event",  re.compile(r"\blisting\b",            re.IGNORECASE)),
    ("ban_event",      re.compile(r"\bban\b",                re.IGNORECASE)),
    ("crash_event",    re.compile(r"\bcrash\b",              re.IGNORECASE)),
    ("rate_cut",       re.compile(r"\brate\s+cut\b",         re.IGNORECASE)),
    ("fed_event",      re.compile(r"\bfed\b|\bfederal\b",    re.IGNORECASE)),
    ("cpi_event",      re.compile(r"\bcpi\b",                re.IGNORECASE)),
    ("interest_rate",  re.compile(r"\binterest\s+rate\b",    re.IGNORECASE)),
]

_POLITICS_RULES: list[tuple[str, re.Pattern]] = [
    ("election",       re.compile(r"\belection\b",           re.IGNORECASE)),
    ("president",      re.compile(r"\bpresident\b",          re.IGNORECASE)),
    ("trump",          re.compile(r"\btrump\b",              re.IGNORECASE)),
    ("biden",          re.compile(r"\bbiden\b",              re.IGNORECASE)),
    ("harris",         re.compile(r"\bharris\b",             re.IGNORECASE)),
    ("congress",       re.compile(r"\bcongress\b",           re.IGNORECASE)),
    ("senate",         re.compile(r"\bsenate\b",             re.IGNORECASE)),
    ("democrat",       re.compile(r"\bdemocrat\w*\b",        re.IGNORECASE)),
    ("republican",     re.compile(r"\brepublican\w*\b",      re.IGNORECASE)),
    ("vote",           re.compile(r"\bvotes?\b|\bvoting\b",   re.IGNORECASE)),
    ("governor",       re.compile(r"\bgovernor\b",           re.IGNORECASE)),
    ("primary",        re.compile(r"\bprimary\b",            re.IGNORECASE)),
    ("ballot",         re.compile(r"\bballot\b",             re.IGNORECASE)),
    ("political",      re.compile(r"\bpolitical\b",          re.IGNORECASE)),
    ("party",          re.compile(r"\bparty\b",              re.IGNORECASE)),
    ("war",            re.compile(r"\bwar\b",                re.IGNORECASE)),
    ("nato",           re.compile(r"\bnato\b",               re.IGNORECASE)),
    ("government",     re.compile(r"\bgovernment\b",         re.IGNORECASE)),
    ("minister",       re.compile(r"\bminister\b",           re.IGNORECASE)),
    ("parliament",     re.compile(r"\bparliament\b",         re.IGNORECASE)),
]

# Asset patterns (for confidence boosting on UPDOWN)
_ASSET_PATTERNS = re.compile(r"\b(BTC|ETH|SOL|XRP|Bitcoin|Ethereum|Solana|Ripple)\b", re.IGNORECASE)
# Timeframe patterns (for confidence boosting on UPDOWN)
_TIMEFRAME_PATTERNS = re.compile(
    r"\b(5\s*m(?:in)?|15\s*m(?:in)?|1\s*[Hh]|1\s*hour|60\s*m(?:in)?)\b", re.IGNORECASE
)


# ── Classifier ────────────────────────────────────────────────────────────────

class EventClassifier:
    """
    Stateless market event classifier.

    Call classify() with a raw market title.  Optionally pass the pre-detected
    asset and timeframe strings (from the discovery engine) so the UPDOWN
    confidence can be boosted when all three signals are present.
    """

    @staticmethod
    def classify(
        title: str,
        *,
        asset: str = "",
        timeframe: str = "",
    ) -> Classification:
        """
        Classify a market title.  Priority: UPDOWN > PRICE_RANGE > NEWS_EVENT > POLITICS > OTHER.
        """
        # ── 1. UPDOWN — highest priority ─────────────────────────────────────
        for rule_name, pattern in _UPDOWN_RULES:
            if pattern.search(title):
                confidence = EventClassifier._updown_confidence(title, asset, timeframe)
                return Classification(
                    event_type=EventType.UPDOWN,
                    confidence=confidence,
                    matched_rule=rule_name,
                )

        # ── 2. PRICE_RANGE ────────────────────────────────────────────────────
        for rule_name, pattern in _PRICE_RANGE_RULES:
            if pattern.search(title):
                return Classification(
                    event_type=EventType.PRICE_RANGE,
                    confidence=0.80,
                    matched_rule=rule_name,
                )

        # ── 3. NEWS_EVENT ─────────────────────────────────────────────────────
        for rule_name, pattern in _NEWS_EVENT_RULES:
            if pattern.search(title):
                return Classification(
                    event_type=EventType.NEWS_EVENT,
                    confidence=0.75,
                    matched_rule=rule_name,
                )

        # ── 4. POLITICS ───────────────────────────────────────────────────────
        for rule_name, pattern in _POLITICS_RULES:
            if pattern.search(title):
                return Classification(
                    event_type=EventType.POLITICS,
                    confidence=0.70,
                    matched_rule=rule_name,
                )

        # ── 5. OTHER ──────────────────────────────────────────────────────────
        return Classification(
            event_type=EventType.OTHER,
            confidence=1.0,
            matched_rule="no_rule_matched",
        )

    @staticmethod
    def _updown_confidence(title: str, asset: str, timeframe: str) -> float:
        """
        Confidence boosting for UPDOWN classification.

        Three signals increase confidence:
          1. Asset detected in title (BTC/ETH/SOL/XRP)
          2. Timeframe detected in title (5m/15m/1H)
          3. Caller already confirmed asset + timeframe (from discovery engine)
        """
        has_asset = bool(asset) or bool(_ASSET_PATTERNS.search(title))
        has_timeframe = bool(timeframe) or bool(_TIMEFRAME_PATTERNS.search(title))
        caller_confirmed = bool(asset) and bool(timeframe)

        if caller_confirmed:
            return 0.95  # discovery engine already validated all three
        if has_asset and has_timeframe:
            return 0.90
        if has_asset or has_timeframe:
            return 0.80
        return 0.65

    @staticmethod
    def classify_bulk(
        titles: list[str],
    ) -> dict[EventType, int]:
        """
        Classify a sequence of titles and return aggregate counts per EventType.
        Used by the discovery engine to accumulate stats across all 250k+ markets
        without storing individual rows.
        """
        counts: dict[EventType, int] = {et: 0 for et in EventType}
        for title in titles:
            result = EventClassifier.classify(title)
            counts[result.event_type] += 1
        return counts
