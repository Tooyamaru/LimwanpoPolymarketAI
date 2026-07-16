"""
Strategy Engine tests — Layer 6.

Covers:
  - _make_decision() pure function: all branches + priority order (15 cases)
  - StrategyEngine.run() with mocked repositories (9 integration cases)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.strategy_engine import (
    _make_decision,
    StrategyEngine,
    SCORE_OPEN,
    SCORE_WATCH,
    SPREAD_THRESHOLD,
    MIN_SIGNAL_CONFIDENCE,
    MIN_SIGNAL_CONFIDENCE_MTF,
)


# ── _make_decision — pure unit tests ─────────────────────────────────────────


def test_skip_high_spread():
    decision, reason = _make_decision(
        score=80.0, direction="BUY_YES", spread_yes=SPREAD_THRESHOLD + 0.001
    )
    assert decision == "SKIP"
    assert reason == "HIGH_SPREAD"


def test_spread_at_threshold_is_not_high_spread():
    """Boundary: spread_yes == SPREAD_THRESHOLD is allowed (rule is strict >)."""
    decision, reason = _make_decision(
        score=80.0,
        direction="BUY_YES",
        spread_yes=SPREAD_THRESHOLD,
        signal_confidence=MIN_SIGNAL_CONFIDENCE + 1.0,
    )
    assert reason != "HIGH_SPREAD"


def test_spread_none_does_not_skip():
    """spread_yes=None means no spread data — not skipped by spread rule."""
    decision, _ = _make_decision(
        score=80.0,
        direction="BUY_YES",
        spread_yes=None,
        signal_confidence=MIN_SIGNAL_CONFIDENCE + 1.0,
    )
    assert decision == "OPEN_LONG_YES"


def test_skip_neutral_direction():
    decision, reason = _make_decision(
        score=80.0, direction="NEUTRAL", spread_yes=0.01
    )
    assert decision == "SKIP"
    assert reason == "NEUTRAL_DIRECTION"


def test_high_spread_takes_priority_over_neutral():
    """SPREAD check runs before NEUTRAL check."""
    decision, reason = _make_decision(
        score=80.0, direction="NEUTRAL", spread_yes=SPREAD_THRESHOLD + 0.01
    )
    assert reason == "HIGH_SPREAD"


def test_skip_low_signal_confidence_blocks_open_long():
    decision, reason = _make_decision(
        score=SCORE_OPEN,
        direction="BUY_YES",
        spread_yes=0.01,
        signal_confidence=MIN_SIGNAL_CONFIDENCE - 0.1,
        mtf_confirmed=False,
    )
    assert decision == "SKIP"
    assert reason == "LOW_SIGNAL_CONFIDENCE"


def test_mtf_confirmed_uses_lower_threshold():
    """MTF-confirmed signal passes at MIN_SIGNAL_CONFIDENCE_MTF, not MIN_SIGNAL_CONFIDENCE."""
    decision, reason = _make_decision(
        score=SCORE_OPEN,
        direction="BUY_YES",
        spread_yes=0.01,
        signal_confidence=MIN_SIGNAL_CONFIDENCE_MTF + 0.1,
        mtf_confirmed=True,
    )
    assert decision == "OPEN_LONG_YES"
    assert reason is None


def test_mtf_confirmed_still_blocked_below_mtf_threshold():
    decision, reason = _make_decision(
        score=SCORE_OPEN,
        direction="BUY_YES",
        spread_yes=0.01,
        signal_confidence=MIN_SIGNAL_CONFIDENCE_MTF - 0.1,
        mtf_confirmed=True,
    )
    assert decision == "SKIP"
    assert reason == "LOW_SIGNAL_CONFIDENCE"


def test_confidence_none_skips_gate():
    """No signal data → confidence gate is not applied; decision proceeds normally."""
    decision, _ = _make_decision(
        score=SCORE_OPEN, direction="BUY_YES", spread_yes=0.01,
        signal_confidence=None,
    )
    assert decision == "OPEN_LONG_YES"


def test_open_long_yes():
    decision, reason = _make_decision(
        score=SCORE_OPEN,
        direction="BUY_YES",
        spread_yes=0.01,
        signal_confidence=MIN_SIGNAL_CONFIDENCE + 1.0,
    )
    assert decision == "OPEN_LONG_YES"
    assert reason is None


def test_open_long_no():
    decision, reason = _make_decision(
        score=SCORE_OPEN,
        direction="BUY_NO",
        spread_yes=0.01,
        signal_confidence=MIN_SIGNAL_CONFIDENCE + 1.0,
    )
    assert decision == "OPEN_LONG_NO"
    assert reason is None


def test_watch_in_mid_band():
    mid_score = (SCORE_WATCH + SCORE_OPEN) / 2
    decision, reason = _make_decision(
        score=mid_score, direction="BUY_YES", spread_yes=0.01
    )
    assert decision == "WATCH"
    assert reason is None


def test_watch_at_score_watch_boundary():
    """SCORE_WATCH itself maps to WATCH (>= check)."""
    decision, reason = _make_decision(
        score=SCORE_WATCH, direction="BUY_YES", spread_yes=0.01
    )
    assert decision == "WATCH"
    assert reason is None


def test_skip_low_score():
    decision, reason = _make_decision(
        score=SCORE_WATCH - 0.1, direction="BUY_YES", spread_yes=0.01
    )
    assert decision == "SKIP"
    assert reason == "LOW_SCORE"


def test_confidence_gate_not_applied_below_score_open():
    """Below SCORE_OPEN the confidence gate is bypassed — produces WATCH, not LOW_SIGNAL_CONFIDENCE."""
    decision, reason = _make_decision(
        score=SCORE_WATCH + 1.0,
        direction="BUY_YES",
        spread_yes=0.01,
        signal_confidence=0.0,  # would fail if gate ran at this score
    )
    assert decision == "WATCH"
    assert reason is None


# ── StrategyEngine.run() — async integration tests ───────────────────────────


def _make_opp(
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    opportunity_score: float = 80.0,
    direction: str = "BUY_YES",
    spread_yes: float = 0.01,
    yes_mid: float = 0.55,
    yes_bid: float = 0.53,
    yes_ask: float = 0.57,
) -> MagicMock:
    opp = MagicMock()
    opp.condition_id = condition_id
    opp.asset = asset
    opp.timeframe = timeframe
    opp.opportunity_score = opportunity_score
    opp.direction = direction
    opp.spread_yes = spread_yes
    opp.yes_mid = yes_mid
    opp.yes_bid = yes_bid
    opp.yes_ask = yes_ask
    return opp


@pytest.mark.anyio
async def test_run_no_opportunities_returns_zero_summary():
    session = AsyncMock()

    with patch(
        "app.services.strategy_engine.opp_repo.get_all_opportunities",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await StrategyEngine().run(session)

    assert result == {
        "opportunities_read": 0,
        "open_long_yes": 0,
        "open_long_no": 0,
        "watch": 0,
        "skip": 0,
        "errors": 0,
        "duration_ms": 0,
    }


@pytest.mark.anyio
async def test_run_open_long_yes_persisted_with_position_size():
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp()]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=25.0),
    ):
        result = await StrategyEngine().run(session)

    assert result["open_long_yes"] == 1
    assert result["open_long_no"] == 0
    assert result["skip"] == 0
    assert result["errors"] == 0
    mock_insert.assert_awaited_once()
    kw = mock_insert.call_args.kwargs
    assert kw["decision"] == "OPEN_LONG_YES"
    assert kw["position_size_usdc"] == 25.0


@pytest.mark.anyio
async def test_run_open_long_no_persisted_with_position_size():
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(direction="BUY_NO")]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=10.0),
    ):
        result = await StrategyEngine().run(session)

    assert result["open_long_no"] == 1
    kw = mock_insert.call_args.kwargs
    assert kw["decision"] == "OPEN_LONG_NO"
    assert kw["position_size_usdc"] == 10.0


@pytest.mark.anyio
async def test_run_skip_not_persisted_by_default():
    """SKIP decisions are not inserted when STRATEGY_PERSIST_SKIPS is False (default)."""
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(opportunity_score=5.0)]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
    ):
        result = await StrategyEngine().run(session)

    assert result["skip"] == 1
    assert result["open_long_yes"] == 0
    mock_insert.assert_not_awaited()


@pytest.mark.anyio
async def test_run_position_sizing_none_demotes_to_skip():
    """PositionSizingService returning None prevents insertion and increments skip."""
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(opportunity_score=80.0)]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=None),
    ):
        result = await StrategyEngine().run(session)

    assert result["open_long_yes"] == 0
    assert result["skip"] == 1
    mock_insert.assert_not_awaited()


@pytest.mark.anyio
async def test_run_signal_confidence_gate_blocks_open_long():
    sig = MagicMock()
    sig.confidence_score = MIN_SIGNAL_CONFIDENCE - 1.0
    sig.mtf_confirmed = False

    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(opportunity_score=80.0)]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=sig),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
    ):
        result = await StrategyEngine().run(session)

    assert result["skip"] == 1
    assert result["open_long_yes"] == 0
    mock_insert.assert_not_awaited()


@pytest.mark.anyio
async def test_run_watch_decision_is_always_persisted():
    """WATCH is not a SKIP — it is always inserted regardless of STRATEGY_PERSIST_SKIPS."""
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(opportunity_score=25.0)]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock) as mock_insert,
    ):
        result = await StrategyEngine().run(session)

    assert result["watch"] == 1
    mock_insert.assert_awaited_once()
    assert mock_insert.call_args.kwargs["decision"] == "WATCH"


@pytest.mark.anyio
async def test_run_insert_exception_counted_as_error():
    """An exception during insert_decision is caught and counted as an error."""
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=[_make_opp(opportunity_score=80.0)]),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock, side_effect=RuntimeError("db down")),
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=25.0),
    ):
        result = await StrategyEngine().run(session)

    # counter was incremented before the failed insert
    assert result["open_long_yes"] == 1
    assert result["errors"] == 1


@pytest.mark.anyio
async def test_run_multiple_opportunities_mixed_results():
    opps = [
        _make_opp("0x1", opportunity_score=80.0, direction="BUY_YES"),  # OPEN_LONG_YES
        _make_opp("0x2", opportunity_score=80.0, direction="BUY_NO"),   # OPEN_LONG_NO
        _make_opp("0x3", opportunity_score=25.0, direction="BUY_YES"),  # WATCH — in [20, 30) band
        _make_opp("0x4", opportunity_score=5.0,  direction="BUY_YES"),  # SKIP
    ]
    session = AsyncMock()

    with (
        patch("app.services.strategy_engine.opp_repo.get_all_opportunities", return_value=opps),
        patch("app.services.strategy_engine.sig_repo.get_last_signal_for_market", new_callable=AsyncMock, return_value=None),
        patch("app.services.strategy_engine.td_repo.insert_decision", new_callable=AsyncMock),
        patch("app.services.strategy_engine._sizing_service.calculate", return_value=25.0),
    ):
        result = await StrategyEngine().run(session)

    assert result["opportunities_read"] == 4
    assert result["open_long_yes"] == 1
    assert result["open_long_no"] == 1
    assert result["watch"] == 1
    assert result["skip"] == 1
    assert result["errors"] == 0
