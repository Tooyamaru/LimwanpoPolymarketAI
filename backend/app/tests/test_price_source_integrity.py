"""
Price Source Integrity Gate Tests — Chainlink RTDS integration.

Tests the _check_price_source_integrity() gate and its integration with
StrategyEngine.run().

Test inventory (12 tests):
  1.  Gate disabled → OPEN_LONG_YES proceeds (no integrity check)
  2.  target_price=None → TARGET_PENDING blocks entry
  3.  target_verified=False → TARGET_UNVERIFIED blocks entry
  4.  Chainlink client=None → REFERENCE_PRICE_UNAVAILABLE blocks entry
  5.  Chainlink client has no price for asset → REFERENCE_PRICE_UNAVAILABLE
  6.  Chainlink price stale → REFERENCE_PRICE_STALE blocks entry
  7.  All good → gate passes (returns True, None)
  8.  Gate is ENTRY-ONLY: WATCH bypasses gate (persisted normally)
  9.  Gate is ENTRY-ONLY: SKIP bypasses gate (not persisted by default)
  10. StrategyEngine.run() respects gate: OPEN_LONG blocked → SKIP counted
  11. StrategyEngine.run() gate disabled → normal OPEN_LONG_YES
  12. target_verified=True + fresh Chainlink → gate passes, sizing proceeds
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_exec_result(rows: list) -> MagicMock:
    """Fake SQLAlchemy execute() result that supports .scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _make_live_market_for_strategy(condition_id: str = "0xabc", asset: str = "BTC",
                                   target_price: float | None = None,
                                   target_verified: bool = False) -> MagicMock:
    """Market with WINDOW_LIVE prediction window fields for strategy engine prefetch."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=60)
    end = start + timedelta(seconds=300)
    m = MagicMock()
    m.condition_id = condition_id
    m.asset = asset
    m.timeframe = "5m"
    m.event_slug = "crypto-5m-test"
    m.prediction_window_start = start
    m.prediction_window_end = end
    m.target_price = target_price
    m.target_verified = target_verified
    m.target_stale = not target_verified
    return m


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_market(
    condition_id: str = "0xabc",
    asset: str = "BTC",
    target_price: float | None = None,
    target_verified: bool = False,
    target_stale: bool = True,
    status: str = "active",
):
    """Create a minimal MarketUniverse mock for integrity gate tests."""
    m = MagicMock()
    m.condition_id = condition_id
    m.asset = asset
    m.timeframe = "5m"
    m.status = status
    m.target_price = target_price
    m.target_verified = target_verified
    m.target_stale = target_stale
    m.target_source = "POLYMARKET_GAMMA" if target_verified else None
    m.target_validation_error = None
    m.opening_price = None
    m.opening_price_source = None
    m.reference_status = "PENDING"
    return m


def _make_fresh_chainlink_client(asset: str = "BTC", value: float = 65000.0):
    """Mock a ChainlinkRTDSClient with a fresh, non-stale price."""
    client = MagicMock()
    price = MagicMock()
    price.asset = asset
    price.value = value
    price.stale = False
    price.age_ms = 100
    price.healthy = True
    client.get_price.return_value = price
    client.is_healthy.return_value = True
    return client


def _make_stale_chainlink_client(asset: str = "BTC"):
    """Mock a ChainlinkRTDSClient with a stale price."""
    client = MagicMock()
    price = MagicMock()
    price.asset = asset
    price.value = 65000.0
    price.stale = True
    price.age_ms = 120_000
    price.healthy = False
    client.get_price.return_value = price
    client.is_healthy.return_value = False
    return client


def _make_opp(
    condition_id: str = "0xabc",
    asset: str = "BTC",
    opportunity_score: float = 80.0,
    direction: str = "BUY_YES",
    spread_yes: float = 0.01,
    yes_mid: float = 0.55,
    yes_bid: float = 0.53,
    yes_ask: float = 0.57,
):
    opp = MagicMock()
    opp.condition_id = condition_id
    opp.asset = asset
    opp.timeframe = "5m"
    opp.opportunity_score = opportunity_score
    opp.direction = direction
    opp.spread_yes = spread_yes
    opp.yes_mid = yes_mid
    opp.yes_bid = yes_bid
    opp.yes_ask = yes_ask
    return opp


# ── Unit tests for _check_price_source_integrity ──────────────────────────────

def test_1_gate_passes_when_verified_and_fresh():
    """Test 1: target_verified=True + fresh Chainlink → gate passes."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(
        target_price=65000.0,
        target_verified=True,
    )
    client = _make_fresh_chainlink_client()
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is True
    assert block_code is None


def test_2_target_price_none_returns_target_pending():
    """Test 2: target_price=None → TARGET_PENDING."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=None, target_verified=False)
    client = _make_fresh_chainlink_client()
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is False
    assert block_code == "TARGET_PENDING"


def test_3_target_unverified_returns_target_unverified():
    """Test 3: target_price set but target_verified=False → TARGET_UNVERIFIED."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=65000.0, target_verified=False)
    client = _make_fresh_chainlink_client()
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is False
    assert block_code == "TARGET_UNVERIFIED"


def test_4_chainlink_client_none_returns_unavailable():
    """Test 4: Chainlink client=None → REFERENCE_PRICE_UNAVAILABLE."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=65000.0, target_verified=True)
    allowed, block_code = _check_price_source_integrity(market, None)
    assert allowed is False
    assert block_code == "REFERENCE_PRICE_UNAVAILABLE"


def test_5_chainlink_no_price_for_asset_returns_unavailable():
    """Test 5: Chainlink client has no price for this asset → REFERENCE_PRICE_UNAVAILABLE."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=65000.0, target_verified=True, asset="ETH")
    client = MagicMock()
    client.get_price.return_value = None
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is False
    assert block_code == "REFERENCE_PRICE_UNAVAILABLE"


def test_6_chainlink_stale_price_returns_stale():
    """Test 6: Chainlink price is stale → REFERENCE_PRICE_STALE."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=65000.0, target_verified=True)
    client = _make_stale_chainlink_client()
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is False
    assert block_code == "REFERENCE_PRICE_STALE"


def test_7_all_good_gate_passes():
    """Test 7: All conditions satisfied → gate passes (True, None)."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=65000.0, target_verified=True)
    client = _make_fresh_chainlink_client()
    allowed, block_code = _check_price_source_integrity(market, client)
    assert allowed is True
    assert block_code is None


def test_8_target_pending_has_priority_over_unverified():
    """Test 8: target_price=None takes TARGET_PENDING priority over verified=False."""
    from app.services.strategy_engine import _check_price_source_integrity
    market = _make_market(target_price=None, target_verified=False)
    client = _make_fresh_chainlink_client()
    allowed, code = _check_price_source_integrity(market, client)
    assert code == "TARGET_PENDING"


# ── Integration tests for StrategyEngine.run() ────────────────────────────────

pytestmark = pytest.mark.anyio


async def test_9_gate_disabled_allows_open_long():
    """Test 9: CHAINLINK_INTEGRITY_GATE_ENABLED=False → OPEN_LONG_YES proceeds."""
    from app.services.strategy_engine import StrategyEngine
    session = AsyncMock()
    opp = _make_opp(opportunity_score=80.0)
    live_market = _make_live_market_for_strategy(condition_id=opp.condition_id, asset=opp.asset)
    session.execute = AsyncMock(return_value=_make_exec_result([live_market]))

    with (
        patch("app.services.strategy_engine.settings") as mock_settings,
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[opp]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock),
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=25.0),
    ):
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = False
        mock_settings.STRATEGY_PERSIST_SKIPS = False
        mock_settings.STRATEGY_SCORE_OPEN = 30.0
        mock_settings.STRATEGY_SCORE_WATCH = 20.0
        mock_settings.STRATEGY_SPREAD_THRESHOLD = 0.02
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE = 20.0
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE_MTF = 15.0
        mock_settings.POSITION_SCORE_MEDIUM = 30.0
        result = await StrategyEngine().run(session)

    assert result["open_long_yes"] == 1
    assert result["skip"] == 0


async def test_10_gate_blocks_open_long_when_target_pending():
    """Test 10: Gate enabled + target_price=None → OPEN_LONG_YES blocked as SKIP."""
    from app.services.strategy_engine import StrategyEngine
    from app.models.market_universe import MarketUniverse
    session = AsyncMock()
    opp = _make_opp(opportunity_score=80.0)
    market = _make_market(target_price=None, target_verified=False)
    market.condition_id = opp.condition_id
    market.status = "active"
    client = _make_fresh_chainlink_client()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [market]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session.execute = AsyncMock(return_value=mock_result)

    with (
        patch("app.services.strategy_engine.settings") as mock_settings,
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[opp]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine.get_chainlink_client", return_value=client),
    ):
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = True
        mock_settings.STRATEGY_PERSIST_SKIPS = False
        mock_settings.STRATEGY_SCORE_OPEN = 30.0
        mock_settings.STRATEGY_SCORE_WATCH = 20.0
        mock_settings.STRATEGY_SPREAD_THRESHOLD = 0.02
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE = 20.0
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE_MTF = 15.0
        mock_settings.POSITION_SCORE_MEDIUM = 30.0
        # session.execute returns the market prefetch; opp_repo patched separately
        result = await StrategyEngine().run(session)

    assert result["skip"] == 1, f"Expected skip=1, got {result}"
    assert result["open_long_yes"] == 0
    mock_insert.assert_not_awaited()


async def test_11_gate_blocks_all_assets_when_chainlink_unavailable():
    """Test 11: Chainlink client=None → all OPEN_LONG_* blocked."""
    from app.services.strategy_engine import StrategyEngine
    session = AsyncMock()
    opps = [
        _make_opp("0x1", asset="BTC", opportunity_score=80.0),
        _make_opp("0x2", asset="ETH", opportunity_score=80.0),
    ]
    markets = [
        _make_market("0x1", asset="BTC", target_price=65000.0, target_verified=True),
        _make_market("0x2", asset="ETH", target_price=3000.0, target_verified=True),
    ]
    for m in markets:
        m.status = "active"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = markets
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session.execute = AsyncMock(return_value=mock_result)

    with (
        patch("app.services.strategy_engine.settings") as mock_settings,
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=opps),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine.get_chainlink_client", return_value=None),
    ):
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = True
        mock_settings.STRATEGY_PERSIST_SKIPS = False
        mock_settings.STRATEGY_SCORE_OPEN = 30.0
        mock_settings.STRATEGY_SCORE_WATCH = 20.0
        mock_settings.STRATEGY_SPREAD_THRESHOLD = 0.02
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE = 20.0
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE_MTF = 15.0
        mock_settings.POSITION_SCORE_MEDIUM = 30.0
        result = await StrategyEngine().run(session)

    assert result["open_long_yes"] == 0, f"Expected open_long_yes=0, got {result}"
    assert result["skip"] == 2
    mock_insert.assert_not_awaited()


async def test_12_gate_passes_for_verified_target_and_fresh_chainlink():
    """Test 12: target_verified=True + fresh Chainlink → OPEN_LONG_YES inserted."""
    from app.services.strategy_engine import StrategyEngine
    session = AsyncMock()
    opp = _make_opp(opportunity_score=80.0)
    market = _make_live_market_for_strategy(
        condition_id=opp.condition_id,
        asset="BTC",
        target_price=65000.0,
        target_verified=True,
    )
    market.status = "active"
    client = _make_fresh_chainlink_client()

    session.execute = AsyncMock(return_value=_make_exec_result([market]))

    with (
        patch("app.services.strategy_engine.settings") as mock_settings,
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[opp]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=25.0),
        patch("app.services.strategy_engine.get_chainlink_client", return_value=client),
    ):
        mock_settings.CHAINLINK_INTEGRITY_GATE_ENABLED = True
        mock_settings.STRATEGY_PERSIST_SKIPS = False
        mock_settings.STRATEGY_SCORE_OPEN = 30.0
        mock_settings.STRATEGY_SCORE_WATCH = 20.0
        mock_settings.STRATEGY_SPREAD_THRESHOLD = 0.02
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE = 20.0
        mock_settings.STRATEGY_MIN_SIGNAL_CONFIDENCE_MTF = 15.0
        mock_settings.POSITION_SCORE_MEDIUM = 30.0
        result = await StrategyEngine().run(session)

    assert result["open_long_yes"] == 1, f"Expected open_long_yes=1, got {result}"
    assert result["skip"] == 0
    mock_insert.assert_awaited_once()
    kw = mock_insert.call_args.kwargs
    assert kw["decision"] == "OPEN_LONG_YES"
    assert kw["position_size_usdc"] == 25.0
