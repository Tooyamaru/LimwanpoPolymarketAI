"""
Source Validator tests — Sprint 5.

Covers:
  - Exact matcher unit tests (Task 4 patterns)
  - ValidatedMarket / ValidationRun dataclass construction
  - SourceValidatorService with mock HTTP
  - API endpoint schema tests
  - Edge cases and boundary conditions

Pure unit / integration tests — no live network calls.
"""

import json
import pytest
import httpx

from app.services.source_validator import (
    SourceValidatorService,
    ValidationRun,
    ValidatedMarket,
    match_exact_patterns,
    is_updown_candidate,
    SOURCE_ENDPOINT,
    CLOB_BASE_URL,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 4 — Exact Matcher unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExactMatcherPatterns:

    def test_matches_up(self):
        assert "up" in match_exact_patterns("Will BTC go up in 5m?")

    def test_matches_down(self):
        assert "down" in match_exact_patterns("ETH down or up 15m")

    def test_matches_up_down_slash(self):
        assert "up_down" in match_exact_patterns("BTC Up/Down 1 Hour")

    def test_matches_higher(self):
        assert "higher" in match_exact_patterns("Will SOL be higher in 15 minutes?")

    def test_matches_lower(self):
        assert "lower" in match_exact_patterns("XRP lower than yesterday in 1 hour?")

    def test_matches_above(self):
        assert "above" in match_exact_patterns("BTC above $70k in 5m?")

    def test_matches_below(self):
        assert "below" in match_exact_patterns("ETH below $3000 in 15 minutes?")

    def test_matches_5_minutes(self):
        assert "5_minutes" in match_exact_patterns("BTC Up or Down 5 minutes")

    def test_matches_5_minutes_singular(self):
        assert "5_minutes" in match_exact_patterns("SOL up or down in 5 minute?")

    def test_matches_15_minutes(self):
        assert "15_minutes" in match_exact_patterns("ETH Down or Up 15 minutes")

    def test_matches_1_hour(self):
        assert "1_hour" in match_exact_patterns("XRP Up or Down 1 hour")

    def test_no_match_on_empty(self):
        assert match_exact_patterns("") == []

    def test_no_match_on_unrelated(self):
        patterns = match_exact_patterns("Will the President win re-election?")
        assert "5_minutes" not in patterns
        assert "up_down" not in patterns

    def test_case_insensitive_up(self):
        assert "up" in match_exact_patterns("BTC UP in 5m")

    def test_case_insensitive_down(self):
        assert "down" in match_exact_patterns("ETH DOWN in 15m")

    def test_multiple_patterns_fire(self):
        found = match_exact_patterns("Will BTC be up or down in 1 hour?")
        assert "up" in found
        assert "down" in found
        assert "1_hour" in found

    def test_is_updown_candidate_true(self):
        candidate, keywords = is_updown_candidate("BTC up or down 5 minutes")
        assert candidate is True
        assert "up" in keywords

    def test_is_updown_candidate_false(self):
        candidate, keywords = is_updown_candidate("Will the Senate pass the bill?")
        assert candidate is False
        assert keywords == ""

    def test_is_updown_candidate_returns_comma_separated(self):
        candidate, keywords = is_updown_candidate("BTC up or down in 1 hour")
        assert candidate is True
        kw_list = [k.strip() for k in keywords.split(",")]
        assert "up" in kw_list
        assert "down" in kw_list

    def test_word_boundary_up_not_in_support(self):
        # "support" contains "up" but \bup\b should NOT match inside a word
        found = match_exact_patterns("BTC will find support at $60k")
        assert "up" not in found

    def test_word_boundary_down_not_in_downtown(self):
        # "downtown" contains "down" but \bdown\b should NOT fire
        found = match_exact_patterns("Event in downtown Chicago")
        assert "down" not in found


# ═══════════════════════════════════════════════════════════════════════════════
# ValidatedMarket / ValidationRun dataclass tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidatedMarketDataclass:

    def _make(self, **kwargs) -> ValidatedMarket:
        defaults = dict(
            source_endpoint=SOURCE_ENDPOINT,
            source_market_id="0xabc",
            condition_id="0xabc",
            title="BTC Up or Down 5 minutes",
            slug="btc-up-or-down-5m",
            source_event_id="evt001",
            detected_asset="BTC",
            detected_timeframe="5m",
            is_updown_candidate=True,
            updown_keywords_found="up, down, 5_minutes",
            matching_rule="exact_BTC + tf_5m",
        )
        defaults.update(kwargs)
        return ValidatedMarket(**defaults)

    def test_creates_validated_market(self):
        vm = self._make()
        assert vm.detected_asset == "BTC"
        assert vm.is_updown_candidate is True

    def test_optional_slug_none(self):
        vm = self._make(slug=None)
        assert vm.slug is None

    def test_optional_event_id_none(self):
        vm = self._make(source_event_id=None)
        assert vm.source_event_id is None

    def test_optional_timeframe_none(self):
        vm = self._make(detected_timeframe=None)
        assert vm.detected_timeframe is None

    def test_source_endpoint_is_clob(self):
        vm = self._make()
        assert "clob.polymarket.com" in vm.source_endpoint


class TestValidationRunDataclass:

    def test_as_dict_keys(self):
        from datetime import datetime, timezone
        run = ValidationRun(
            run_id="abc-123",
            run_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="clob",
            total_scanned=1000,
            total_asset_matched=50,
            total_updown_candidates=12,
            btc_candidates=5,
            eth_candidates=3,
            sol_candidates=2,
            xrp_candidates=2,
        )
        d = run.as_dict()
        assert d["source"] == "clob"
        assert d["total_scanned"] == 1000
        assert d["total_asset_matched"] == 50
        assert d["total_updown_candidates"] == 12
        assert d["btc_candidates"] == 5
        assert "run_id" in d
        assert "run_at" in d

    def test_markets_defaults_empty_list(self):
        from datetime import datetime, timezone
        run = ValidationRun(
            run_id="x", run_at=datetime.now(timezone.utc),
            source="clob", total_scanned=0,
            total_asset_matched=0, total_updown_candidates=0,
        )
        assert run.markets == []


# ═══════════════════════════════════════════════════════════════════════════════
# SourceValidatorService with mock HTTP
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_PAGE = {
    "data": [
        {
            "condition_id": "0xbtcup5m",
            "question": "Will BTC be up or down in 5 minutes?",
            "market_slug": "btc-up-down-5m",
            "event_id": "ev001",
            "liquidity": 9000.0,
            "volume": 4000.0,
            "end_date_iso": None,
            "tokens": [
                {"outcome": "Yes", "price": 0.52},
                {"outcome": "No", "price": 0.48},
            ],
        },
        {
            "condition_id": "0xeth15m",
            "question": "ETH Up or Down in 15 minutes?",
            "market_slug": "eth-up-down-15m",
            "event_id": "ev002",
            "liquidity": 5000.0,
            "volume": 2000.0,
            "end_date_iso": None,
            "tokens": [],
        },
        {
            "condition_id": "0xsol1h",
            "question": "SOL higher or lower in 1 hour?",
            "market_slug": "sol-higher-lower-1h",
            "event_id": None,
            "liquidity": 3000.0,
            "volume": 1000.0,
            "end_date_iso": None,
            "tokens": [],
        },
        {
            "condition_id": "0xxrpabove",
            "question": "Will XRP be above $0.70 in 15 minutes?",
            "market_slug": "xrp-above-0-70",
            "event_id": "ev004",
            "liquidity": 1000.0,
            "volume": 500.0,
            "end_date_iso": None,
            "tokens": [],
        },
        {
            "condition_id": "0xnomatch",
            "question": "Will the US CPI beat expectations?",
            "market_slug": "cpi-beat",
            "event_id": "ev005",
            "liquidity": 200.0,
            "volume": 100.0,
            "end_date_iso": None,
            "tokens": [],
        },
    ],
    "next_cursor": "",
}


class MockValidatorTransport(httpx.AsyncBaseTransport):
    def __init__(self, page_data: dict = MOCK_PAGE):
        self._page_data = page_data

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(self._page_data).encode(),
            headers={"Content-Type": "application/json"},
        )


@pytest.fixture
def validator_with_mock() -> SourceValidatorService:
    svc = SourceValidatorService()
    svc._client = httpx.AsyncClient(
        base_url=CLOB_BASE_URL,
        transport=MockValidatorTransport(),
    )
    return svc


@pytest.mark.anyio
async def test_validate_returns_run(validator_with_mock):
    run = await validator_with_mock.validate()
    assert isinstance(run, ValidationRun)


@pytest.mark.anyio
async def test_validate_source_is_clob(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.source == "clob"


@pytest.mark.anyio
async def test_validate_run_id_is_uuid(validator_with_mock):
    import uuid
    run = await validator_with_mock.validate()
    parsed = uuid.UUID(run.run_id)
    assert str(parsed) == run.run_id


@pytest.mark.anyio
async def test_validate_total_scanned(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.total_scanned == 5  # 5 items in mock page


@pytest.mark.anyio
async def test_validate_asset_matched_excludes_no_match(validator_with_mock):
    run = await validator_with_mock.validate()
    # CPI market has no asset match → excluded
    assert run.total_asset_matched == 4


@pytest.mark.anyio
async def test_validate_updown_candidates_count(validator_with_mock):
    run = await validator_with_mock.validate()
    # BTC(up/down), ETH(up/down), SOL(higher/lower), XRP(above) → all 4 are candidates
    assert run.total_updown_candidates == 4


@pytest.mark.anyio
async def test_validate_btc_candidate_count(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.btc_candidates == 1


@pytest.mark.anyio
async def test_validate_eth_candidate_count(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.eth_candidates == 1


@pytest.mark.anyio
async def test_validate_sol_candidate_count(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.sol_candidates == 1


@pytest.mark.anyio
async def test_validate_xrp_candidate_count(validator_with_mock):
    run = await validator_with_mock.validate()
    assert run.xrp_candidates == 1


@pytest.mark.anyio
async def test_validate_market_has_source_endpoint(validator_with_mock):
    run = await validator_with_mock.validate()
    for m in run.markets:
        assert "clob.polymarket.com" in m.source_endpoint


@pytest.mark.anyio
async def test_validate_market_has_condition_id(validator_with_mock):
    run = await validator_with_mock.validate()
    btc = next(m for m in run.markets if m.detected_asset == "BTC")
    assert btc.condition_id == "0xbtcup5m"
    assert btc.source_market_id == "0xbtcup5m"


@pytest.mark.anyio
async def test_validate_market_slug_captured(validator_with_mock):
    run = await validator_with_mock.validate()
    btc = next(m for m in run.markets if m.detected_asset == "BTC")
    assert btc.slug == "btc-up-down-5m"


@pytest.mark.anyio
async def test_validate_market_event_id_captured(validator_with_mock):
    run = await validator_with_mock.validate()
    btc = next(m for m in run.markets if m.detected_asset == "BTC")
    assert btc.source_event_id == "ev001"


@pytest.mark.anyio
async def test_validate_market_event_id_none_when_missing(validator_with_mock):
    run = await validator_with_mock.validate()
    sol = next(m for m in run.markets if m.detected_asset == "SOL")
    assert sol.source_event_id is None


@pytest.mark.anyio
async def test_validate_market_updown_keywords_populated(validator_with_mock):
    run = await validator_with_mock.validate()
    btc = next(m for m in run.markets if m.detected_asset == "BTC")
    assert btc.updown_keywords_found != ""
    assert "up" in btc.updown_keywords_found


@pytest.mark.anyio
async def test_validate_market_matching_rule_has_asset(validator_with_mock):
    run = await validator_with_mock.validate()
    btc = next(m for m in run.markets if m.detected_asset == "BTC")
    assert "BTC" in btc.matching_rule


@pytest.mark.anyio
async def test_validate_empty_page():
    svc = SourceValidatorService()
    svc._client = httpx.AsyncClient(
        base_url=CLOB_BASE_URL,
        transport=MockValidatorTransport({"data": [], "next_cursor": ""}),
    )
    run = await svc.validate()
    assert run.total_scanned == 0
    assert run.total_asset_matched == 0
    assert run.total_updown_candidates == 0
    assert run.markets == []


@pytest.mark.anyio
async def test_validate_run_at_is_utc(validator_with_mock):
    from datetime import timezone
    run = await validator_with_mock.validate()
    assert run.run_at.tzinfo is not None


@pytest.mark.anyio
async def test_process_raw_market_returns_none_on_missing_condition_id():
    svc = SourceValidatorService()
    result = svc._process_raw_market({"question": "BTC up or down 5m", "condition_id": ""})
    assert result is None


@pytest.mark.anyio
async def test_process_raw_market_returns_none_on_missing_title():
    svc = SourceValidatorService()
    result = svc._process_raw_market({"question": "", "condition_id": "0xabc"})
    assert result is None


@pytest.mark.anyio
async def test_process_raw_market_returns_none_on_no_asset_match():
    svc = SourceValidatorService()
    result = svc._process_raw_market({
        "question": "Will Federer win Wimbledon?",
        "condition_id": "0xtennis",
    })
    assert result is None


@pytest.mark.anyio
async def test_process_raw_market_btc_detected():
    svc = SourceValidatorService()
    result = svc._process_raw_market({
        "question": "Will BTC be up or down in 5 minutes?",
        "condition_id": "0xbtc001",
        "market_slug": "btc-5m",
        "event_id": "evt1",
    })
    assert result is not None
    assert result.detected_asset == "BTC"
    assert result.is_updown_candidate is True


@pytest.mark.anyio
async def test_process_raw_market_timeframe_detected():
    svc = SourceValidatorService()
    result = svc._process_raw_market({
        "question": "ETH Up or Down in 15 minutes?",
        "condition_id": "0xeth001",
    })
    assert result is not None
    assert result.detected_timeframe == "15m"


@pytest.mark.anyio
async def test_process_raw_market_no_timeframe_still_stored():
    svc = SourceValidatorService()
    result = svc._process_raw_market({
        "question": "BTC up or down today?",
        "condition_id": "0xbtcday",
    })
    assert result is not None
    assert result.detected_timeframe is None


# ═══════════════════════════════════════════════════════════════════════════════
# API endpoint schema tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_diagnostics_endpoint_schema(client):
    resp = await client.get("/api/v1/source-validation")
    assert resp.status_code == 200
    body = resp.json()
    assert "source" in body
    assert "markets" in body
    assert body["source"] == "clob"
    assert isinstance(body["markets"], int)


@pytest.mark.anyio
async def test_diagnostics_markets_non_negative(client):
    resp = await client.get("/api/v1/source-validation")
    assert resp.status_code == 200
    assert resp.json()["markets"] >= 0


@pytest.mark.anyio
async def test_search_endpoint_requires_q(client):
    resp = await client.get("/api/v1/source-validation/search")
    assert resp.status_code == 422  # missing required query param


@pytest.mark.anyio
async def test_search_endpoint_returns_list(client):
    resp = await client.get("/api/v1/source-validation/search?q=btc")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_search_result_schema(client):
    resp = await client.get("/api/v1/source-validation/search?q=btc")
    assert resp.status_code == 200
    results = resp.json()
    for item in results:
        assert "title" in item
        assert "slug" in item
        assert "market_id" in item
        assert "event_id" in item


@pytest.mark.anyio
async def test_audit_endpoint_returns_list(client):
    resp = await client.get("/api/v1/source-validation/audit")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_audit_result_schema(client):
    resp = await client.get("/api/v1/source-validation/audit")
    assert resp.status_code == 200
    for item in resp.json():
        assert "run_id" in item
        assert "title" in item
        assert "condition_id" in item
        assert "source_endpoint" in item
        assert "is_updown_candidate" in item
        assert item["is_updown_candidate"] is True


@pytest.mark.anyio
async def test_audit_all_results_are_candidates(client):
    resp = await client.get("/api/v1/source-validation/audit")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["is_updown_candidate"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Source constant tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_source_endpoint_constant():
    assert SOURCE_ENDPOINT == "https://clob.polymarket.com/markets"


def test_clob_base_url_constant():
    assert CLOB_BASE_URL == "https://clob.polymarket.com"
