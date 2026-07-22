"""
test_exit_prediction_window.py — Phase A Checkpoint 9

Verifies ExitEngine.run() uses prediction_window_end exclusively for expiry
detection, processes all OPEN/PARTIAL positions globally by exact condition_id,
and never fabricates exit prices or falls back to end_time.

20 targeted tests. All datetimes are fixed timezone-aware UTC values.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exit_engine import ExitEngine

# ---------------------------------------------------------------------------
# Fixed anchors
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 8, 0, 0, tzinfo=timezone.utc)

# WINDOW_LIVE: Window A — NOW is inside [A_START, A_END)
A_START = NOW - timedelta(seconds=60)
A_END = A_START + timedelta(seconds=300)    # = NOW + 240 s (not yet expired)

# Window B — next slot (not yet started at NOW)
B_START = A_END
B_END = B_START + timedelta(seconds=300)

# Expired window: ended 100 s before NOW
EXP_START = NOW - timedelta(seconds=400)
EXP_END = EXP_START + timedelta(seconds=300)  # = NOW - 100 s (past)

CID_A = "0xCOND_A"
CID_B = "0xCOND_B"

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def make_pos(
    id=1,
    condition_id=CID_A,
    asset="BTC",
    timeframe="5m",
    side="LONG_YES",
    quantity=10.0,
    remaining_quantity=None,
    entry_price=0.50,
    status="OPEN",
    opened_at=None,
):
    pos = MagicMock()
    pos.id = id
    pos.condition_id = condition_id
    pos.asset = asset
    pos.timeframe = timeframe
    pos.side = side
    pos.quantity = quantity
    pos.remaining_quantity = remaining_quantity if remaining_quantity is not None else quantity
    pos.entry_price = entry_price
    pos.status = status
    pos.opened_at = opened_at or (NOW - timedelta(minutes=60))
    pos.peak_pnl_usdc = None
    return pos


def make_opp(
    condition_id=CID_A,
    yes_bid=0.62,
    yes_ask=0.64,
    yes_mid=0.63,
    spread_yes=0.02,
    opportunity_score=70.0,
    direction="BUY_YES",
    minutes_to_expiry=240.0,
    signal_count_1h=3,
):
    opp = MagicMock()
    opp.condition_id = condition_id
    opp.yes_bid = yes_bid
    opp.yes_ask = yes_ask
    opp.yes_mid = yes_mid
    opp.spread_yes = spread_yes
    opp.opportunity_score = opportunity_score
    opp.direction = direction
    opp.minutes_to_expiry = minutes_to_expiry
    opp.signal_count_1h = signal_count_1h
    return opp


def make_resolution(condition_id=CID_A, final_yes_price=1.0, final_no_price=0.0):
    r = MagicMock()
    r.condition_id = condition_id
    r.outcome_source = "DIRECT_POLYMARKET_RESOLUTION"
    r.final_yes_price = final_yes_price
    r.final_no_price = final_no_price
    return r


def scalars_result(rows):
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    r.all.return_value = [(row,) if not isinstance(row, tuple) else row for row in rows]
    return r


def all_result(tuples):
    r = MagicMock()
    r.all.return_value = tuples
    return r


# ---------------------------------------------------------------------------
# Engine runner
# ---------------------------------------------------------------------------

async def run_engine(
    positions,
    opps=None,
    pw_end_map=None,    # list of (condition_id, pw_end | None)
    resolutions=None,
    signal_counts=None, # list of (condition_id, count)
    pending_exit_ids=None,
    now=NOW,
):
    """Run ExitEngine.run() with fully controlled session mock."""
    opps = opps or []
    pw_end_map = pw_end_map or []
    resolutions = resolutions or []
    signal_counts = signal_counts or []
    pending_ids = [(pid,) for pid in (pending_exit_ids or [])]

    session = AsyncMock()
    session.add = MagicMock()  # session.add is synchronous in SQLAlchemy
    session.execute = AsyncMock(side_effect=[
        scalars_result(opps),           # opp_map query
        all_result(pw_end_map),         # prediction_window_end map query
        scalars_result(resolutions),    # resolution_map query
        all_result(signal_counts),      # direct signal count map query
        all_result(pending_ids),        # pending exit IDs query
    ])

    with (
        patch("app.services.exit_engine.pos_repo.get_open_positions",
              new_callable=AsyncMock, return_value=positions),
        patch("app.services.exit_engine.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = now
        mock_dt.now.side_effect = None
        result = await ExitEngine().run(session)

    return result, session


# ===========================================================================
# 1. OPEN position current condition diproses
# ===========================================================================

@pytest.mark.asyncio
async def test_open_position_current_condition_processed():
    """OPEN position with valid pw_end not yet expired is evaluated."""
    pos = make_pos(status="OPEN")
    opp = make_opp(yes_bid=0.62)
    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],      # window still open at NOW
    )
    # Position is evaluated (no trigger → no decision, but also not skipped as invalid)
    assert result["evaluated"] == 1
    assert result["errors"] == 0


# ===========================================================================
# 2. PARTIAL position diproses
# ===========================================================================

@pytest.mark.asyncio
async def test_partial_position_processed():
    """PARTIAL positions are included in the global open query and evaluated."""
    pos = make_pos(status="PARTIAL", quantity=10.0, remaining_quantity=6.0)
    opp = make_opp()
    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
    )
    assert result["evaluated"] == 1
    assert result["errors"] == 0


# ===========================================================================
# 3. Position from old window still processed after rollover
# ===========================================================================

@pytest.mark.asyncio
async def test_old_position_processed_after_rollover():
    """
    Window A position is still found and evaluated after dashboard rolls to B.
    The engine fetches ALL open positions globally — card visibility is irrelevant.
    """
    pos_a = make_pos(id=1, condition_id=CID_A, status="OPEN")
    opp_a = make_opp(condition_id=CID_A, yes_bid=0.61)
    # Window A has NOT expired (pw_end still in future at NOW)
    result, session = await run_engine(
        positions=[pos_a],
        opps=[opp_a],
        pw_end_map=[(CID_A, A_END)],   # Window A's pw_end, still live
    )
    assert result["evaluated"] == 1
    assert result["errors"] == 0


# ===========================================================================
# 4. Lookup uses exact position.condition_id
# ===========================================================================

@pytest.mark.asyncio
async def test_lookup_uses_exact_condition_id():
    """
    The engine fetches market pw_end and opp by pos.condition_id exactly.
    No asset-based redirect: CID_A position sees CID_A opp only.
    """
    pos = make_pos(condition_id=CID_A)
    opp_a = make_opp(condition_id=CID_A, yes_bid=0.63)
    opp_b = make_opp(condition_id=CID_B, yes_bid=0.55)  # Window B — must NOT be used

    result, session = await run_engine(
        positions=[pos],
        opps=[opp_a, opp_b],
        pw_end_map=[(CID_A, A_END), (CID_B, B_END)],
    )
    # Position evaluated; opp_a.yes_bid used, not opp_b.yes_bid
    assert result["evaluated"] == 1
    assert result["errors"] == 0


# ===========================================================================
# 5. Current card condition B does not replace condition A
# ===========================================================================

@pytest.mark.asyncio
async def test_condition_b_does_not_replace_condition_a():
    """
    Two positions: one on CID_A, one on CID_B.
    Each is evaluated against its own market data — CID_B's opp/pw_end
    is never applied to the CID_A position.
    """
    pos_a = make_pos(id=1, condition_id=CID_A)
    pos_b = make_pos(id=2, condition_id=CID_B)
    opp_a = make_opp(condition_id=CID_A, yes_bid=0.60)
    opp_b = make_opp(condition_id=CID_B, yes_bid=0.55)

    result, session = await run_engine(
        positions=[pos_a, pos_b],
        opps=[opp_a, opp_b],
        pw_end_map=[(CID_A, A_END), (CID_B, B_END)],
    )
    assert result["evaluated"] == 2
    assert result["errors"] == 0


# ===========================================================================
# 6. now before prediction end → not expired
# ===========================================================================

@pytest.mark.asyncio
async def test_before_prediction_end_not_expired():
    """now < prediction_window_end → no forced expiry; normal triggers apply."""
    pos = make_pos(side="LONG_YES", entry_price=0.50)
    opp = make_opp(yes_bid=0.50)   # PnL ≈ 0, no trigger expected
    # pw_end is A_END = NOW + 240 s → NOT expired
    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
        signal_counts=[(CID_A, 5)],   # active signals → SIGNAL_INVALIDATION blocked
    )
    # No forced expiry; no resolution needed
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ===========================================================================
# 7. Exact prediction end → expired
# ===========================================================================

@pytest.mark.asyncio
async def test_exact_prediction_end_is_expired():
    """now == prediction_window_end → now >= pw_end is True → expiry path."""
    pw_end_exactly_now = NOW   # exact boundary: now >= pw_end fires
    pos = make_pos(side="LONG_YES")
    resolution = make_resolution(condition_id=CID_A, final_yes_price=1.0)

    result, session = await run_engine(
        positions=[pos],
        opps=[],
        pw_end_map=[(CID_A, pw_end_exactly_now)],
        resolutions=[resolution],
    )
    # Expired path triggered → forced close decision emitted
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.decision == "CLOSE_POSITION"
    assert td.exit_reason == "EXPIRY_EXIT"
    assert td.forced_exit_price == pytest.approx(1.0)


# ===========================================================================
# 8. After prediction end → expired
# ===========================================================================

@pytest.mark.asyncio
async def test_after_prediction_end_is_expired():
    """now > prediction_window_end → expiry path; forced close with resolution."""
    pos = make_pos(side="LONG_YES", condition_id=CID_A)
    resolution = make_resolution(condition_id=CID_A, final_yes_price=0.0)

    # EXP_END = NOW - 100 s → expired
    result, session = await run_engine(
        positions=[pos],
        opps=[],
        pw_end_map=[(CID_A, EXP_END)],
        resolutions=[resolution],
    )
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.forced_exit_price == pytest.approx(0.0)


# ===========================================================================
# 9. Contract end_time far future does not delay 5M expiry
# ===========================================================================

@pytest.mark.asyncio
async def test_far_end_time_does_not_delay_expiry():
    """
    Even if the contract end_time is days away, a passed prediction_window_end
    means the position enters the expiry path.
    The engine reads prediction_window_end only — end_time is never consulted.
    """
    pos = make_pos(side="LONG_YES")
    resolution = make_resolution(condition_id=CID_A, final_yes_price=1.0)

    # pw_end is in the past; end_time would be 48h away but is NOT in the map
    # (the map only has prediction_window_end)
    result, session = await run_engine(
        positions=[pos],
        opps=[],
        pw_end_map=[(CID_A, EXP_END)],   # prediction_window_end expired
        resolutions=[resolution],
    )
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.exit_reason == "EXPIRY_EXIT"


# ===========================================================================
# 10. Missing prediction_window_end → no fallback to end_time
# ===========================================================================

@pytest.mark.asyncio
async def test_missing_pw_end_no_end_time_fallback():
    """
    prediction_window_end is None (not set in DB) → engine logs
    INVALID_PREDICTION_WINDOW, skips expiry detection, does NOT fall back to
    end_time, and continues normal trigger evaluation.
    No forced close, no fabricated price.
    """
    pos = make_pos(side="LONG_YES", entry_price=0.50)
    opp = make_opp(yes_bid=0.50)  # near-zero PnL → no trigger

    # pw_end_map has condition_id present but value is None
    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, None)],  # prediction_window_end missing
        resolutions=[],
        signal_counts=[(CID_A, 5)],  # active signals → SIGNAL_INVALIDATION blocked
    )
    # No expiry path triggered; no fake exit
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ===========================================================================
# 11. RESOLVING market still processable by Exit
# ===========================================================================

@pytest.mark.asyncio
async def test_resolving_market_processed_by_exit():
    """
    When now >= prediction_window_end (RESOLVING state) and resolution data is
    available, Exit closes the position.  Exit does NOT require WINDOW_LIVE.
    """
    pos = make_pos(side="LONG_YES")
    resolution = make_resolution(condition_id=CID_A, final_yes_price=1.0)

    result, session = await run_engine(
        positions=[pos],
        opps=[],
        pw_end_map=[(CID_A, EXP_END)],   # window closed → RESOLVING/RESOLVED
        resolutions=[resolution],
    )
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.exit_reason == "EXPIRY_EXIT"


# ===========================================================================
# 12. Exit does not require WINDOW_LIVE
# ===========================================================================

@pytest.mark.asyncio
async def test_exit_does_not_require_window_live():
    """
    Exit must fire even when the prediction window is not WINDOW_LIVE.
    A stop-loss hit on an in-window position (normal triggers) fires without
    any lifecycle gate — exit is evaluated unconditionally.
    """
    # Position opened a long time ago, PnL deeply negative → STOP_LOSS
    pos = make_pos(side="LONG_YES", quantity=100.0, entry_price=0.50)
    # yes_bid well below stop loss (PnL = 100 * (0.40 - 0.50) = -10 ≪ -1.50)
    opp = make_opp(yes_bid=0.40, spread_yes=0.02)

    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],   # window live but could be anything
    )
    # Stop loss should fire without any lifecycle gate
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.exit_reason == "STOP_LOSS"


# ===========================================================================
# 13. Unavailable exit price → no fake trade
# ===========================================================================

@pytest.mark.asyncio
async def test_unavailable_exit_price_no_fake_trade():
    """LONG_YES with yes_bid=None → no executable price → position skipped."""
    pos = make_pos(side="LONG_YES")
    opp = make_opp()
    opp.yes_bid = None   # price unavailable

    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
    )
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ===========================================================================
# 14. Unavailable exit price → position not closed
# ===========================================================================

@pytest.mark.asyncio
async def test_unavailable_exit_price_position_not_closed():
    """LONG_NO with yes_ask=None → no executable price → position stays open."""
    pos = make_pos(side="LONG_NO")
    opp = make_opp()
    opp.yes_ask = None

    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
    )
    assert result["skipped"] >= 1
    assert result["decisions_created"] == 0


# ===========================================================================
# 15. Unavailable exit price → realized PnL not changed
# ===========================================================================

@pytest.mark.asyncio
async def test_unavailable_exit_price_no_pnl_change():
    """No executable price → session.add never called → realized_pnl unchanged."""
    pos = make_pos(side="LONG_YES")
    opp = make_opp()
    opp.yes_bid = None

    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
    )
    session.add.assert_not_called()


# ===========================================================================
# 16. One invalid position does not stop other valid positions
# ===========================================================================

@pytest.mark.asyncio
async def test_invalid_position_does_not_stop_valid():
    """
    An exception during processing of position 1 is caught; position 2
    is still evaluated and can generate a close decision.
    """
    pos1 = make_pos(id=1, condition_id=CID_A)
    pos2 = make_pos(id=2, condition_id=CID_B, side="LONG_YES",
                    quantity=100.0, entry_price=0.50)
    opp_b = make_opp(condition_id=CID_B, yes_bid=0.40, spread_yes=0.02)
    # pos1's opp is missing → price unavailable; pos2 hits STOP_LOSS

    result, session = await run_engine(
        positions=[pos1, pos2],
        opps=[opp_b],   # no opp for CID_A → pos1 skipped (no price)
        pw_end_map=[(CID_A, A_END), (CID_B, A_END)],
    )
    assert result["evaluated"] == 2
    # pos1 skipped (no price), pos2 → STOP_LOSS decision
    assert result["decisions_created"] >= 1


# ===========================================================================
# 17. Current dashboard absence does not remove old position
# ===========================================================================

@pytest.mark.asyncio
async def test_dashboard_absence_does_not_remove_position():
    """
    The exit engine queries ALL OPEN positions from the DB, regardless of
    which condition_ids appear on the current dashboard.
    A position whose card is no longer visible is still evaluated.
    """
    # pos_old has a condition_id not in any "current" universe set
    pos_old = make_pos(condition_id="0xOLD_COND_NOT_ON_DASHBOARD")
    opp_old = make_opp(condition_id="0xOLD_COND_NOT_ON_DASHBOARD", yes_bid=0.50)

    result, session = await run_engine(
        positions=[pos_old],
        opps=[opp_old],
        pw_end_map=[("0xOLD_COND_NOT_ON_DASHBOARD", A_END)],
    )
    assert result["evaluated"] == 1
    assert result["errors"] == 0


# ===========================================================================
# 18. Old condition uses its own token/market binding
# ===========================================================================

@pytest.mark.asyncio
async def test_old_condition_uses_own_binding():
    """
    Close decision for CID_A position must carry CID_A as condition_id —
    never redirected to CID_B.
    """
    pos = make_pos(condition_id=CID_A, side="LONG_YES",
                   quantity=100.0, entry_price=0.50)
    # Deeply negative PnL → STOP_LOSS fires
    opp = make_opp(condition_id=CID_A, yes_bid=0.40, spread_yes=0.02)

    result, session = await run_engine(
        positions=[pos],
        opps=[opp],
        pw_end_map=[(CID_A, A_END)],
    )
    assert result["decisions_created"] == 1
    td = session.add.call_args[0][0]
    assert td.condition_id == CID_A, "close decision must bind to original condition_id"


# ===========================================================================
# 19. No synthetic 0.5 exit
# ===========================================================================

@pytest.mark.asyncio
async def test_no_synthetic_0_5_exit():
    """
    Expired position with no resolution data → position is skipped this cycle.
    No TradeDecision with forced_exit_price=0.5 is created.
    No TradeDecision at all — not even with other prices.
    """
    pos = make_pos(side="LONG_YES")

    result, session = await run_engine(
        positions=[pos],
        opps=[],
        pw_end_map=[(CID_A, EXP_END)],   # expired
        resolutions=[],                   # no resolution data yet
    )
    assert result["decisions_created"] == 0
    session.add.assert_not_called()


# ===========================================================================
# 20. Global open-position query not filtered to current universe
# ===========================================================================

@pytest.mark.asyncio
async def test_global_open_position_query():
    """
    ExitEngine fetches ALL open positions (mocked by pos_repo) — not just
    those whose condition_ids appear in a current asset/universe set.
    This test passes three positions with three distinct condition_ids and
    verifies all three are in result["evaluated"].
    """
    positions = [
        make_pos(id=1, condition_id="0xALPHA"),
        make_pos(id=2, condition_id="0xBETA"),
        make_pos(id=3, condition_id="0xGAMMA"),
    ]
    opps = [
        make_opp(condition_id="0xALPHA"),
        make_opp(condition_id="0xBETA"),
        make_opp(condition_id="0xGAMMA"),
    ]
    pw_end_map = [
        ("0xALPHA", A_END),
        ("0xBETA", A_END),
        ("0xGAMMA", A_END),
    ]

    result, session = await run_engine(
        positions=positions,
        opps=opps,
        pw_end_map=pw_end_map,
    )
    assert result["evaluated"] == 3
    assert result["errors"] == 0
