"""
Risk Engine tests — Layers 9, 14, and 16.

Covers:
  - _check_market_entry_rules(): multi-entry admission rules 1a-1f (7 cases)
  - _check_rules(): rules 2-9 + all-pass case (9 cases)
  - RiskEngine.evaluate(): Pass 1 (entry) + Pass 2 (exit) (8 cases)
"""

from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.risk_engine import RiskEngine
from app.config.settings import settings


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_td(
    id: int = 1,
    condition_id: str = "0xabc",
    asset: str = "BTC",
    timeframe: str = "5m",
    decision: str = "OPEN_LONG_YES",
    status: str = "PENDING",
    position_size_usdc: float = 10.0,
    exit_reason: str | None = None,
) -> MagicMock:
    td = MagicMock()
    td.id = id
    td.condition_id = condition_id
    td.asset = asset
    td.timeframe = timeframe
    td.decision = decision
    td.status = status
    td.position_size_usdc = position_size_usdc
    td.exit_reason = exit_reason
    return td


def _make_pos(
    condition_id: str = "0xother",
    asset: str = "BTC",
    timeframe: str = "5m",
    status: str = "OPEN",
    quantity: float = 1.0,
    entry_price: float = 10.0,
    unrealized_pnl: float = 0.0,
    side: str = "LONG_YES",
    remaining_quantity: float | None = None,
    opened_at: datetime | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.condition_id = condition_id
    pos.asset = asset
    pos.timeframe = timeframe
    pos.status = status
    pos.quantity = quantity
    pos.remaining_quantity = remaining_quantity if remaining_quantity is not None else quantity
    pos.entry_price = entry_price
    pos.unrealized_pnl = unrealized_pnl
    pos.side = side
    pos.opened_at = opened_at or (datetime.now(timezone.utc) - timedelta(hours=1))
    return pos


def _make_exec_result(rows: list) -> MagicMock:
    """Fake SQLAlchemy execute() result that supports .scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _make_live_market(condition_id: str = "0xabc") -> MagicMock:
    """Market fixture with timezone-aware WINDOW_LIVE prediction window."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=60)
    end = start + timedelta(seconds=300)
    m = MagicMock()
    m.condition_id = condition_id
    m.prediction_window_start = start
    m.prediction_window_end = end
    return m


def _make_capital_status(allowed: bool = True, reason: str | None = None) -> MagicMock:
    status = MagicMock()
    status.allowed = allowed
    status.reason = reason
    return status


# ── _check_market_entry_rules — multi-entry admission (Rule 1a-1f) ────────────


def test_market_entry_rules_all_pass_for_fresh_market():
    td = _make_td(condition_id="0xnew", decision="OPEN_LONG_YES")
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=[], now=datetime.now(timezone.utc), incoming_usdc=5.0,
        lifetime_entry_counts={},
    )
    assert result is None


def test_rule1a_opposite_side_conflict():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    positions = [_make_pos(condition_id="0xabc", side="LONG_NO")]
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=positions, now=datetime.now(timezone.utc), incoming_usdc=5.0,
        lifetime_entry_counts={"0xabc": 1},
    )
    assert result == "OPPOSITE_SIDE_CONFLICT"


def test_rule1a_same_side_scale_in_allowed():
    """Multiple entries on the SAME side of a market are the whole point of
    multi-entry support — this must never be blocked as a duplicate."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=positions, now=datetime.now(timezone.utc), incoming_usdc=5.0,
        lifetime_entry_counts={"0xabc": 1},
    )
    assert result is None




def test_rule1e_max_exposure_per_market_usdc():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES", position_size_usdc=1.0)
    limit = settings.MAX_EXPOSURE_PER_MARKET_USDC
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES", quantity=1.0, entry_price=limit - 0.5)]
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=positions, now=datetime.now(timezone.utc), incoming_usdc=1.0,
        lifetime_entry_counts={"0xabc": 1},
    )
    assert result == "MAX_EXPOSURE_PER_MARKET"


def test_rule1f_cooldown_active():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    now = datetime.now(timezone.utc)
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES", opened_at=now - timedelta(seconds=1))]
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=positions, now=now, incoming_usdc=1.0,
        lifetime_entry_counts={"0xabc": 1},
    )
    assert result == "COOLDOWN_ACTIVE"


def test_rule1f_cooldown_elapsed_allows_entry():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    now = datetime.now(timezone.utc)
    positions = [_make_pos(
        condition_id="0xabc", side="LONG_YES",
        opened_at=now - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
    )]
    result = RiskEngine._check_market_entry_rules(
        td, open_positions=positions, now=now, incoming_usdc=1.0,
        lifetime_entry_counts={"0xabc": 1},
    )
    assert result is None


# ── _check_rules — Layer 9 ────────────────────────────────────────────────────


def test_check_rules_all_pass_returns_none():
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", asset="BTC", timeframe="5m", position_size_usdc=5.0)
    open_positions: list = []
    assert engine._check_rules(td, open_positions, daily_trades=0, daily_loss=0.0) is None




def test_check_rule4_daily_loss():
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew")
    # settings.MAX_DAILY_LOSS = -50.0 by default
    result = engine._check_rules(
        td, [], daily_trades=0, daily_loss=settings.MAX_DAILY_LOSS
    )
    assert result == "DAILY_LOSS"


def test_check_rule5_daily_trades():
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew")
    # settings.MAX_DAILY_TRADES = 20 by default
    result = engine._check_rules(
        td, [], daily_trades=settings.MAX_DAILY_TRADES, daily_loss=0.0
    )
    assert result == "DAILY_TRADES"


# ── _check_rules — Layer 14 ───────────────────────────────────────────────────


def test_check_rule6_portfolio_exposure_limit():
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", position_size_usdc=1.0)
    # Each position contributes quantity * entry_price to total exposure
    # Fill total_exposure just below limit, then incoming_usdc pushes it over
    limit = settings.PORTFOLIO_MAX_EXPOSURE_USDC  # 200.0
    # One big position covering (limit - 0.5) USDC
    positions = [_make_pos(condition_id="0xother", quantity=1.0, entry_price=limit - 0.5)]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result == "PORTFOLIO_EXPOSURE_LIMIT"




def test_check_rule8_asset_exposure_limit():
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", asset="SOL", position_size_usdc=1.0)
    # Fill asset exposure just below limit for SOL
    asset_limit = settings.PORTFOLIO_MAX_PER_ASSET_USDC  # 100.0
    positions = [
        _make_pos(condition_id="0xother", asset="SOL", quantity=1.0, entry_price=asset_limit - 0.5)
    ]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result == "ASSET_EXPOSURE_LIMIT"




# ── RiskEngine.evaluate() ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_evaluate_no_pending_returns_zero_summary():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([]),   # no entry decisions
        _make_exec_result([]),   # no exit decisions
    ])

    result = await RiskEngine().evaluate(session)

    assert result["evaluated"] == 0
    assert result["allowed"] == 0
    assert result["blocked"] == 0
    assert result["exit_approved"] == 0
    assert result["errors"] == 0


@pytest.mark.anyio
async def test_evaluate_entry_decision_approved():
    td = _make_td(decision="OPEN_LONG_YES", status="PENDING")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([td]),                         # entry decisions
        _make_exec_result([_make_live_market("0xabc")]), # MarketUniverse batch
        _make_exec_result([]),                           # no exits
    ])
    capital_ok = _make_capital_status(allowed=True)

    with (
        patch("app.services.capital_management_service.CapitalManagementService") as MockCapSvc,
        patch.object(RiskEngine, "_get_open_positions", new_callable=AsyncMock, return_value=[]),
        patch.object(RiskEngine, "_get_daily_trades_count", new_callable=AsyncMock, return_value=0),
        patch.object(RiskEngine, "_get_daily_unrealized_loss", new_callable=AsyncMock, return_value=0.0),
        patch.object(RiskEngine, "_get_available_capital", new_callable=AsyncMock, return_value=999.0),
        patch.object(RiskEngine, "_get_previous_entry_decisions", new_callable=AsyncMock, return_value={}),
        patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock),
    ):
        MockCapSvc.return_value.evaluate = AsyncMock(return_value=capital_ok)
        result = await RiskEngine().evaluate(session)

    assert result["evaluated"] == 1
    assert result["allowed"] == 1
    assert result["blocked"] == 0
    assert td.status == "RISK_APPROVED"


@pytest.mark.anyio
async def test_evaluate_entry_decision_blocked_by_rule():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES", status="PENDING")
    # One open position on the OPPOSITE side of the same market → blocked by
    # the multi-entry admission rule (OPPOSITE_SIDE_CONFLICT)
    existing = _make_pos(condition_id="0xabc", side="LONG_NO")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([td]),                         # entry decisions
        _make_exec_result([_make_live_market("0xabc")]), # MarketUniverse batch
        _make_exec_result([]),                           # no exits
    ])
    capital_ok = _make_capital_status(allowed=True)

    with (
        patch("app.services.capital_management_service.CapitalManagementService") as MockCapSvc,
        patch.object(RiskEngine, "_get_open_positions", new_callable=AsyncMock, return_value=[existing]),
        patch.object(RiskEngine, "_get_daily_trades_count", new_callable=AsyncMock, return_value=0),
        patch.object(RiskEngine, "_get_daily_unrealized_loss", new_callable=AsyncMock, return_value=0.0),
        patch.object(RiskEngine, "_get_available_capital", new_callable=AsyncMock, return_value=999.0),
        patch.object(RiskEngine, "_get_previous_entry_decisions", new_callable=AsyncMock, return_value={}),
        patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock),
    ):
        MockCapSvc.return_value.evaluate = AsyncMock(return_value=capital_ok)
        result = await RiskEngine().evaluate(session)

    assert result["evaluated"] == 1
    assert result["blocked"] == 1
    assert result["allowed"] == 0
    assert td.status == "BLOCKED"


@pytest.mark.anyio
async def test_evaluate_capital_gate_blocks_all_entries():
    td1 = _make_td(id=1, decision="OPEN_LONG_YES", status="PENDING")
    td2 = _make_td(id=2, decision="OPEN_LONG_NO", status="PENDING")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([td1, td2]),                              # entry decisions
        _make_exec_result([_make_live_market("0xabc")]),            # MarketUniverse batch
        _make_exec_result([]),                                      # no exits
    ])
    capital_blocked = _make_capital_status(allowed=False, reason="DAILY_LOSS_LIMIT")

    with (
        patch("app.services.capital_management_service.CapitalManagementService") as MockCapSvc,
        patch.object(RiskEngine, "_get_open_positions", new_callable=AsyncMock, return_value=[]),
        patch.object(RiskEngine, "_get_daily_trades_count", new_callable=AsyncMock, return_value=0),
        patch.object(RiskEngine, "_get_daily_unrealized_loss", new_callable=AsyncMock, return_value=0.0),
        patch.object(RiskEngine, "_get_available_capital", new_callable=AsyncMock, return_value=999.0),
        patch.object(RiskEngine, "_get_previous_entry_decisions", new_callable=AsyncMock, return_value={}),
        patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock),
    ):
        MockCapSvc.return_value.evaluate = AsyncMock(return_value=capital_blocked)
        result = await RiskEngine().evaluate(session)

    assert result["evaluated"] == 2
    assert result["blocked"] == 2
    assert result["allowed"] == 0
    assert td1.status == "BLOCKED"
    assert td2.status == "BLOCKED"


@pytest.mark.anyio
async def test_evaluate_exit_decision_auto_approved():
    td = _make_td(decision="CLOSE_POSITION", status="PENDING", exit_reason="PROFIT_TARGET")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([]),   # no entry decisions
        _make_exec_result([td]), # one exit decision
    ])

    with patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock):
        result = await RiskEngine().evaluate(session)

    assert result["exit_approved"] == 1
    assert result["evaluated"] == 0
    assert result["allowed"] == 0
    assert result["blocked"] == 0
    assert td.status == "RISK_APPROVED"


@pytest.mark.anyio
async def test_evaluate_mixed_entry_and_exit():
    entry = _make_td(id=1, decision="OPEN_LONG_YES", status="PENDING")
    exit_td = _make_td(id=2, decision="CLOSE_POSITION", status="PENDING", exit_reason="TIMEOUT")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([entry]),                       # entry decisions
        _make_exec_result([_make_live_market("0xabc")]), # MarketUniverse batch
        _make_exec_result([exit_td]),                    # exit decisions
    ])
    capital_ok = _make_capital_status(allowed=True)

    with (
        patch("app.services.capital_management_service.CapitalManagementService") as MockCapSvc,
        patch.object(RiskEngine, "_get_open_positions", new_callable=AsyncMock, return_value=[]),
        patch.object(RiskEngine, "_get_daily_trades_count", new_callable=AsyncMock, return_value=0),
        patch.object(RiskEngine, "_get_daily_unrealized_loss", new_callable=AsyncMock, return_value=0.0),
        patch.object(RiskEngine, "_get_available_capital", new_callable=AsyncMock, return_value=999.0),
        patch.object(RiskEngine, "_get_previous_entry_decisions", new_callable=AsyncMock, return_value={}),
        patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock),
    ):
        MockCapSvc.return_value.evaluate = AsyncMock(return_value=capital_ok)
        result = await RiskEngine().evaluate(session)

    assert result["evaluated"] == 1
    assert result["allowed"] == 1
    assert result["exit_approved"] == 1
    assert result["errors"] == 0
    assert entry.status == "RISK_APPROVED"
    assert exit_td.status == "RISK_APPROVED"


@pytest.mark.anyio
async def test_evaluate_entry_exception_counted_as_error():
    td = _make_td(decision="OPEN_LONG_YES", status="PENDING")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([td]),                         # entry decisions
        _make_exec_result([_make_live_market("0xabc")]), # MarketUniverse batch
        _make_exec_result([]),                           # no exits
    ])
    capital_ok = _make_capital_status(allowed=True)

    with (
        patch("app.services.capital_management_service.CapitalManagementService") as MockCapSvc,
        patch.object(RiskEngine, "_get_open_positions", new_callable=AsyncMock, return_value=[]),
        patch.object(RiskEngine, "_get_daily_trades_count", new_callable=AsyncMock, return_value=0),
        patch.object(RiskEngine, "_get_daily_unrealized_loss", new_callable=AsyncMock, return_value=0.0),
        patch.object(RiskEngine, "_get_available_capital", new_callable=AsyncMock, return_value=999.0),
        patch.object(RiskEngine, "_get_previous_entry_decisions", new_callable=AsyncMock, return_value={}),
        patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock, side_effect=RuntimeError("db error")),
    ):
        MockCapSvc.return_value.evaluate = AsyncMock(return_value=capital_ok)
        result = await RiskEngine().evaluate(session)

    assert result["errors"] == 1
    # allowed counter is incremented before the persist call that raises;
    # it stays at 1 — the exception fires during create_risk_event, not before
    assert result["allowed"] == 1


@pytest.mark.anyio
async def test_evaluate_exit_exception_counted_as_error():
    td = _make_td(decision="CLOSE_POSITION", status="PENDING")
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _make_exec_result([]),
        _make_exec_result([td]),
    ])

    with patch("app.services.risk_engine.risk_repo.create_risk_event", new_callable=AsyncMock, side_effect=RuntimeError("db error")):
        result = await RiskEngine().evaluate(session)

    assert result["errors"] == 1
    assert result["exit_approved"] == 0


# ── SCALE_IN_NO_IMPROVEMENT — rule 1g (Phase 12J) ────────────────────────────
#
# Helper: build a lightweight TradeDecision-like mock for previous_entry_decisions.

def _make_prev(
    condition_id: str = "0xabc",
    opportunity_score: float = 32.0,
    yes_mid: float | None = 0.55,
    decision: str = "OPEN_LONG_YES",
) -> MagicMock:
    prev = MagicMock()
    prev.condition_id = condition_id
    prev.opportunity_score = opportunity_score
    prev.yes_mid = yes_mid
    prev.decision = decision
    return prev


# --- 1. First entry always allowed (no market positions → gate skipped) -------

def test_scale_in_gate_first_entry_no_positions_always_allowed():
    """No open positions for this market → first entry → 1g is never evaluated."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 30.0
    td.yes_mid = 0.55
    prev = _make_prev("0xabc", opportunity_score=30.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=[],  # no existing lots → first entry
        now=datetime.now(timezone.utc),
        incoming_usdc=10.0,
        lifetime_entry_counts={},
        previous_entry_decisions={"0xabc": prev},  # prev exists but no positions → skipped
    )
    assert result is None


# --- 2. Second entry with opportunity_score improvement allowed ----------------

def test_scale_in_gate_opportunity_improvement_allows_entry():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 36.0  # prev=32.0, delta=4 >= SCALE_IN_MIN_OPPORTUNITY_DELTA=3
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result is None


# --- 3. Second entry: opportunity_score at exact threshold allowed -------------

def test_scale_in_gate_opportunity_at_exact_threshold_allowed():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 32.0 + settings.SCALE_IN_MIN_OPPORTUNITY_DELTA  # exact threshold
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result is None


# --- 4. Better entry price (lower yes_mid for LONG_YES) allows scale-in -------

def test_scale_in_gate_better_entry_price_yes_allows():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 32.0  # no score improvement
    # yes_mid dropped by 0.01 (> SCALE_IN_ENTRY_PRICE_IMPROVEMENT=0.005) → cheaper YES
    td.yes_mid = 0.55 - settings.SCALE_IN_ENTRY_PRICE_IMPROVEMENT - 0.001
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55, decision="OPEN_LONG_YES")
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result is None


# --- 5. Better entry price for LONG_NO (higher yes_mid) allows scale-in -------

def test_scale_in_gate_better_entry_price_no_allows():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_NO")
    td.opportunity_score = 32.0  # no score improvement
    # yes_mid rose by more than threshold → cheaper NO contract
    td.yes_mid = 0.45 + settings.SCALE_IN_ENTRY_PRICE_IMPROVEMENT + 0.001
    positions = [_make_pos(condition_id="0xabc", side="LONG_NO")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.45, decision="OPEN_LONG_NO")
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result is None


# --- 6. Identical score/price → blocked: SCALE_IN_NO_IMPROVEMENT -------------

def test_scale_in_gate_identical_quality_blocked():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 32.0  # same as prev
    td.yes_mid = 0.55             # same as prev
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result == "SCALE_IN_NO_IMPROVEMENT"


# --- 7. Lower opportunity score → blocked ------------------------------------

def test_scale_in_gate_lower_score_blocked():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 29.0  # lower than prev 32.0
    td.yes_mid = 0.55             # same yes_mid — no price improvement either
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result == "SCALE_IN_NO_IMPROVEMENT"


# --- 8. Score improved but below delta → blocked unless price compensates -----

def test_scale_in_gate_insufficient_score_delta_blocked():
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    # delta = 1 < SCALE_IN_MIN_OPPORTUNITY_DELTA=3; price unchanged
    td.opportunity_score = 33.0
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    prev = _make_prev("0xabc", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result == "SCALE_IN_NO_IMPROVEMENT"


# --- 9. Old/different condition_id not used for current market ----------------

def test_scale_in_gate_rollover_different_condition_id_ignored():
    """The previous_entry_decisions dict uses the exact current condition_id as key.
    A different condition_id (old rollover market) is never matched."""
    td = _make_td(condition_id="0xNEW", decision="OPEN_LONG_YES")
    td.opportunity_score = 32.0
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xNEW", side="LONG_YES")]
    # Only the OLD condition_id is in the dict — not 0xNEW
    prev = _make_prev("0xOLD", opportunity_score=32.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xNEW": 1},
        previous_entry_decisions={"0xOLD": prev},  # different key → no match for 0xNEW
    )
    # No prev_td found → gate skipped → no block from rule 1g
    assert result is None


# --- 10. BLOCKED previous decisions are excluded from the lookup ---------------

def test_scale_in_gate_blocked_previous_not_considered():
    """BLOCKED decisions are filtered out at the repository level.
    If the dict is empty (no RISK_APPROVED/EXECUTED prev), gate is skipped."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 30.0
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    # Empty dict simulates no RISK_APPROVED/EXECUTED previous decision found
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={},  # BLOCKED prev not in dict → no match
    )
    assert result is None  # gate not triggered — no prior confirmed entry


# --- 11. Current decision cannot be compared to itself ------------------------

def test_scale_in_gate_no_self_comparison():
    """PENDING decisions (including the current one) are never in
    previous_entry_decisions (which only holds RISK_APPROVED/EXECUTED rows).
    If the dict is empty for this condition_id, the gate is skipped."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES", status="PENDING")
    td.opportunity_score = 31.0
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    # current decision is PENDING → cannot appear in the dict → empty for 0xabc
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={},  # current PENDING not in dict → no self-compare
    )
    assert result is None


# --- 12. Cooldown fires independently (before rule 1g) -----------------------

def test_scale_in_gate_cooldown_evaluated_independently():
    """Rule 1f (COOLDOWN_ACTIVE) fires before 1g.  Even if score improved,
    the cooldown block takes precedence."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 38.0   # big improvement
    td.yes_mid = 0.50
    now = datetime.now(timezone.utc)
    # last entry was only 1 second ago → cooldown active
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES", opened_at=now - timedelta(seconds=1))]
    prev = _make_prev("0xabc", opportunity_score=30.0, yes_mid=0.55)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=now,
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result == "COOLDOWN_ACTIVE"


# --- 13. Exposure cap fires independently (before rule 1g) -------------------

def test_scale_in_gate_exposure_cap_evaluated_independently():
    """Rule 1e (MAX_EXPOSURE_PER_MARKET) fires before 1g."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES", position_size_usdc=1.0)
    td.opportunity_score = 40.0  # improved
    td.yes_mid = 0.50
    limit = settings.MAX_EXPOSURE_PER_MARKET_USDC
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES", quantity=1.0, entry_price=limit - 0.5)]
    prev = _make_prev("0xabc", opportunity_score=30.0)
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=1.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions={"0xabc": prev},
    )
    assert result == "MAX_EXPOSURE_PER_MARKET"


# --- 14. None previous_entry_decisions skips rule 1g entirely ----------------

def test_scale_in_gate_none_previous_dict_skips_gate():
    """When previous_entry_decisions=None (e.g. caller didn't supply it),
    rule 1g is skipped entirely — backward compatible with existing tests."""
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES")
    td.opportunity_score = 30.0
    td.yes_mid = 0.55
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES")]
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=10.0,
        lifetime_entry_counts={"0xabc": 1},
        previous_entry_decisions=None,  # explicit None → gate skipped
    )
    assert result is None


# ── UNLIMITED POSITION COUNT (Phase 12L) ─────────────────────────────────────
#
# Verifies that fixed count limits no longer block entries and that exposure /
# capital guards remain active.


def test_unlimited_count_5_positions_allowed_if_exposure_safe():
    """5 open positions on different markets allowed — no count cap."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", asset="BTC", timeframe="5m", position_size_usdc=5.0)
    # 5 existing positions on different markets with zero exposure (quantity=0)
    positions = [
        _make_pos(condition_id=f"0xmkt{i}", asset=f"ASSET{i}", quantity=0.0, entry_price=0.0)
        for i in range(5)
    ]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result is None


def test_unlimited_count_20_positions_allowed_if_exposure_safe():
    """20 open positions on different markets allowed — no count cap."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", asset="BTC", timeframe="5m", position_size_usdc=5.0)
    positions = [
        _make_pos(condition_id=f"0xmkt{i}", asset=f"ASSET{i}", quantity=0.0, entry_price=0.0)
        for i in range(20)
    ]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result is None


def test_unlimited_count_no_fixed_count_block_reason():
    """PORTFOLIO_POSITION_LIMIT and MAX_OPEN_POSITIONS are never returned."""
    engine = RiskEngine()
    banned_reasons = {
        "PORTFOLIO_POSITION_LIMIT", "MAX_OPEN_POSITIONS",
        "MAX_ENTRIES_PER_MARKET", "MAX_OPEN_LOTS_PER_MARKET",
        "MAX_SAME_SIDE_ENTRIES", "TIMEFRAME_POSITION_LIMIT",
        "MAX_EXPOSURE",  # old count-based asset-exposure reason
    }
    td = _make_td(condition_id="0xnew", asset="BTC", timeframe="5m", position_size_usdc=1.0)
    # Pile on 50 zero-exposure positions — any count-based block would fire here
    positions = [
        _make_pos(condition_id=f"0xmkt{i}", asset=f"ASSET{i}", quantity=0.0, entry_price=0.0)
        for i in range(50)
    ]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result not in banned_reasons


def test_total_exposure_still_blocks_after_unlimited_count():
    """PORTFOLIO_EXPOSURE_LIMIT still fires even with no count cap."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", position_size_usdc=1.0)
    limit = settings.PORTFOLIO_MAX_EXPOSURE_USDC
    # Single position that fills exposure right up to just below the limit
    positions = [_make_pos(condition_id="0xother", quantity=1.0, entry_price=limit - 0.5)]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result == "PORTFOLIO_EXPOSURE_LIMIT"


def test_per_market_exposure_still_blocks_after_unlimited_count():
    """MAX_EXPOSURE_PER_MARKET still fires — USDC cap per condition_id."""
    limit = settings.MAX_EXPOSURE_PER_MARKET_USDC
    td = _make_td(condition_id="0xabc", decision="OPEN_LONG_YES", position_size_usdc=1.0)
    positions = [_make_pos(condition_id="0xabc", side="LONG_YES", quantity=1.0, entry_price=limit - 0.5)]
    result = RiskEngine._check_market_entry_rules(
        td,
        open_positions=positions,
        now=datetime.now(timezone.utc) - timedelta(seconds=settings.MIN_SECONDS_BETWEEN_ENTRIES + 5),
        incoming_usdc=1.0,
    )
    assert result == "MAX_EXPOSURE_PER_MARKET"


def test_per_asset_exposure_still_blocks_after_unlimited_count():
    """ASSET_EXPOSURE_LIMIT still fires — USDC cap per asset."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", asset="SOL", position_size_usdc=1.0)
    asset_limit = settings.PORTFOLIO_MAX_PER_ASSET_USDC
    positions = [
        _make_pos(condition_id="0xother", asset="SOL", quantity=1.0, entry_price=asset_limit - 0.5)
    ]
    result = engine._check_rules(td, positions, daily_trades=0, daily_loss=0.0)
    assert result == "ASSET_EXPOSURE_LIMIT"


def test_insufficient_capital_blocks_entry():
    """INSUFFICIENT_CAPITAL fires when available_capital - proposed < reserve."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", position_size_usdc=15.0)
    # available_capital = 12.0; reserve = 10.0; 12.0 - 15.0 = -3.0 < 10.0 → BLOCK
    result = engine._check_rules(
        td, [], daily_trades=0, daily_loss=0.0,
        available_capital=12.0,
    )
    assert result == "INSUFFICIENT_CAPITAL"


def test_capital_sufficient_allows_entry():
    """No INSUFFICIENT_CAPITAL when available_capital - proposed >= reserve."""
    engine = RiskEngine()
    td = _make_td(condition_id="0xnew", position_size_usdc=10.0)
    # available_capital = 100.0; reserve = 10.0; 100.0 - 10.0 = 90.0 >= 10.0 → ALLOW
    result = engine._check_rules(
        td, [], daily_trades=0, daily_loss=0.0,
        available_capital=100.0,
    )
    assert result is None


def test_capital_check_skipped_when_none():
    """When available_capital is not passed (None), INSUFFICIENT_CAPITAL is skipped.
    Preserves backward compatibility with direct _check_rules test callers."""
    engine = RiskEngine()
    # Use a tiny position size well within all exposure caps so the ONLY possible
    # block would be INSUFFICIENT_CAPITAL — which should be skipped when None.
    td = _make_td(condition_id="0xnew", position_size_usdc=1.0)
    result = engine._check_rules(
        td, [], daily_trades=0, daily_loss=0.0,
        available_capital=None,
    )
    assert result is None


def test_in_batch_capital_tracked_running():
    """Concurrent approvals in a batch each consume capital from running_capital,
    preventing over-allocation when multiple decisions are processed together.
    Verifies the INSUFFICIENT_CAPITAL block fires on the Nth decision in batch
    even when the first N-1 pass individually."""
    engine = RiskEngine()
    # Each decision requests 40 USDC; available_capital = 90; reserve = 10
    # Decision 1: 90 - 40 = 50 >= 10 → ALLOW; running_capital → 50
    # Decision 2: 50 - 40 = 10 >= 10 → ALLOW; running_capital → 10
    # Decision 3: 10 - 40 = -30 < 10 → INSUFFICIENT_CAPITAL
    td = _make_td(condition_id="0xnew", position_size_usdc=40.0)
    # Test the rule directly at each running_capital level
    assert engine._check_rules(td, [], daily_trades=0, daily_loss=0.0, available_capital=90.0) is None
    assert engine._check_rules(td, [], daily_trades=0, daily_loss=0.0, available_capital=50.0) is None
    assert engine._check_rules(td, [], daily_trades=0, daily_loss=0.0, available_capital=10.0) == "INSUFFICIENT_CAPITAL"
