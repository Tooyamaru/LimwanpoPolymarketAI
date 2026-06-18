"""
Event classifier tests — Sprint 4.

Covers all EventType classifications, confidence levels, bulk classification,
and edge cases. Pure unit tests — no DB, no HTTP.
"""

import pytest

from app.services.event_classifier import Classification, EventClassifier, EventType


# ── UPDOWN detection ──────────────────────────────────────────────────────────

class TestUpdownClassification:
    def test_classic_up_or_down(self):
        clf = EventClassifier.classify("Will BTC be Up or Down in 5m?")
        assert clf.event_type == EventType.UPDOWN

    def test_down_or_up_variant(self):
        clf = EventClassifier.classify("ETH Down or Up in 15 minutes?")
        assert clf.event_type == EventType.UPDOWN

    def test_up_slash_down(self):
        clf = EventClassifier.classify("SOL Up/Down in 1H?")
        assert clf.event_type == EventType.UPDOWN

    def test_up_or_down_case_insensitive(self):
        clf = EventClassifier.classify("btc UP OR DOWN 5m")
        assert clf.event_type == EventType.UPDOWN

    def test_updown_compound(self):
        clf = EventClassifier.classify("XRP updown market 1 hour")
        assert clf.event_type == EventType.UPDOWN

    def test_up_or_down_xrp(self):
        clf = EventClassifier.classify("XRP Up or Down 1 Hour")
        assert clf.event_type == EventType.UPDOWN

    def test_up_or_down_sol(self):
        clf = EventClassifier.classify("SOL Up or Down 15 Minutes")
        assert clf.event_type == EventType.UPDOWN

    def test_updown_returns_classification_object(self):
        clf = EventClassifier.classify("BTC Up or Down 5m")
        assert isinstance(clf, Classification)
        assert clf.matched_rule != ""
        assert 0.0 < clf.confidence <= 1.0


# ── UPDOWN confidence ─────────────────────────────────────────────────────────

class TestUpdownConfidence:
    def test_full_context_caller_confirmed(self):
        """Caller passes asset + timeframe → highest confidence."""
        clf = EventClassifier.classify("BTC Up or Down 5m", asset="BTC", timeframe="5m")
        assert clf.confidence == 0.95

    def test_asset_and_timeframe_in_title(self):
        """Asset + timeframe detectable from title → 0.90."""
        clf = EventClassifier.classify("BTC Up or Down in 5m")
        assert clf.confidence == 0.90

    def test_asset_only_in_title(self):
        """Only asset detectable → 0.80."""
        clf = EventClassifier.classify("BTC Up or Down market")
        assert clf.confidence == 0.80

    def test_timeframe_only_in_title(self):
        """Only timeframe detectable → 0.80."""
        clf = EventClassifier.classify("Price Up or Down in 1H")
        assert clf.confidence == 0.80

    def test_no_context_fallback(self):
        """Neither asset nor timeframe → 0.65."""
        clf = EventClassifier.classify("Up or Down market")
        assert clf.confidence == 0.65


# ── PRICE_RANGE detection ─────────────────────────────────────────────────────

class TestPriceRangeClassification:
    def test_above_keyword(self):
        clf = EventClassifier.classify("Will BTC be above $70,000?")
        assert clf.event_type == EventType.PRICE_RANGE

    def test_below_keyword(self):
        clf = EventClassifier.classify("ETH below $4,000?")
        assert clf.event_type == EventType.PRICE_RANGE

    def test_dollar_amount(self):
        clf = EventClassifier.classify("Will SOL hit $150?")
        assert clf.event_type == EventType.PRICE_RANGE

    def test_between_range(self):
        clf = EventClassifier.classify("Will XRP be between $0.50-$0.60?")
        assert clf.event_type == EventType.PRICE_RANGE

    def test_gt_price(self):
        clf = EventClassifier.classify("BTC > 65000 end of week?")
        assert clf.event_type == EventType.PRICE_RANGE

    def test_over_keyword(self):
        clf = EventClassifier.classify("ETH over $5,000 by Friday?")
        assert clf.event_type == EventType.PRICE_RANGE


# ── NEWS_EVENT detection ──────────────────────────────────────────────────────

class TestNewsEventClassification:
    def test_etf_event(self):
        clf = EventClassifier.classify("Will Bitcoin ETF be approved this week?")
        assert clf.event_type == EventType.NEWS_EVENT

    def test_halving_event(self):
        clf = EventClassifier.classify("BTC halving before July 2024?")
        assert clf.event_type == EventType.NEWS_EVENT

    def test_upgrade_event(self):
        clf = EventClassifier.classify("Ethereum upgrade this quarter?")
        assert clf.event_type == EventType.NEWS_EVENT

    def test_regulation_event(self):
        clf = EventClassifier.classify("Will crypto regulation pass in 2024?")
        assert clf.event_type == EventType.NEWS_EVENT

    def test_approval_event(self):
        clf = EventClassifier.classify("SEC approval for spot ETF?")
        assert clf.event_type == EventType.NEWS_EVENT


# ── POLITICS detection ────────────────────────────────────────────────────────

class TestPoliticsClassification:
    def test_election(self):
        clf = EventClassifier.classify("Who will win the 2024 US election?")
        assert clf.event_type == EventType.POLITICS

    def test_trump(self):
        clf = EventClassifier.classify("Will Trump win the presidency?")
        assert clf.event_type == EventType.POLITICS

    def test_senate(self):
        clf = EventClassifier.classify("Which party controls the Senate in 2025?")
        assert clf.event_type == EventType.POLITICS

    def test_vote(self):
        clf = EventClassifier.classify("Will the bill pass with 60 votes?")
        assert clf.event_type == EventType.POLITICS

    def test_war(self):
        clf = EventClassifier.classify("Will the war end in 2024?")
        assert clf.event_type == EventType.POLITICS


# ── OTHER fallback ────────────────────────────────────────────────────────────

class TestOtherClassification:
    def test_unrecognised_market(self):
        clf = EventClassifier.classify("Will the Super Bowl go to overtime?")
        assert clf.event_type == EventType.OTHER

    def test_other_has_full_confidence(self):
        clf = EventClassifier.classify("Random sports question?")
        assert clf.event_type == EventType.OTHER
        assert clf.confidence == 1.0

    def test_other_rule_name(self):
        clf = EventClassifier.classify("Unknown market with no keywords")
        assert clf.matched_rule == "no_rule_matched"


# ── Priority ordering ─────────────────────────────────────────────────────────

class TestClassificationPriority:
    def test_updown_beats_price_range(self):
        """'Up or Down' with a dollar amount → UPDOWN wins."""
        clf = EventClassifier.classify("BTC Up or Down above $70k in 5m?")
        assert clf.event_type == EventType.UPDOWN

    def test_updown_beats_news(self):
        """'Up or Down' with ETF mention → UPDOWN wins."""
        clf = EventClassifier.classify("BTC Up or Down after ETF approval in 1H?")
        assert clf.event_type == EventType.UPDOWN

    def test_updown_beats_politics(self):
        """'Up or Down' with political context → UPDOWN wins."""
        clf = EventClassifier.classify("BTC Up or Down after election results?")
        assert clf.event_type == EventType.UPDOWN

    def test_price_range_beats_news(self):
        """Price marker with ETF news → PRICE_RANGE wins (it's a price question)."""
        clf = EventClassifier.classify("Will BTC be above $70k after ETF approval?")
        assert clf.event_type == EventType.PRICE_RANGE


# ── classify_bulk ─────────────────────────────────────────────────────────────

class TestClassifyBulk:
    def test_bulk_returns_all_keys(self):
        counts = EventClassifier.classify_bulk([
            "BTC Up or Down 5m",
            "ETH above $4000",
            "Who wins the election?",
        ])
        assert set(counts.keys()) == set(EventType)

    def test_bulk_counts_correctly(self):
        titles = [
            "BTC Up or Down 5m",          # UPDOWN
            "ETH Up or Down 15m",          # UPDOWN
            "SOL above $200?",             # PRICE_RANGE
            "Will Trump win?",             # POLITICS
            "Unknown market",              # OTHER
        ]
        counts = EventClassifier.classify_bulk(titles)
        assert counts[EventType.UPDOWN] == 2
        assert counts[EventType.PRICE_RANGE] == 1
        assert counts[EventType.POLITICS] == 1
        assert counts[EventType.OTHER] == 1

    def test_bulk_empty_list(self):
        counts = EventClassifier.classify_bulk([])
        assert all(v == 0 for v in counts.values())

    def test_bulk_all_other(self):
        titles = ["sports question", "weather question", "random trivia"]
        counts = EventClassifier.classify_bulk(titles)
        assert counts[EventType.OTHER] == 3
