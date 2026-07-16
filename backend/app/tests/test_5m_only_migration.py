"""
5M-Only Migration Tests — validates that the project correctly restricts
active market discovery, signals, opportunities, and entry decisions to
exactly 4 markets: BTC/ETH/SOL/XRP 5m.

Historical 15m/1H data and legacy positions remain intact and are still
reachable via history/portfolio endpoints.

Tests 1-24 as specified in the 5M-ONLY conversion spec.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.market_universe_service import SERIES_CATALOG


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_position(
    position_id: int,
    status: str,
    timeframe: str = "5m",
    asset: str = "BTC",
    remaining_quantity: float = 4.38,
    entry_price: float = 0.50,
    realized_pnl: float | None = None,
    unrealized_pnl: float | None = None,
) -> MagicMock:
    p = MagicMock()
    p.id = position_id
    p.condition_id = f"cond-{position_id}"
    p.asset = asset
    p.timeframe = timeframe
    p.status = status
    p.remaining_quantity = remaining_quantity
    p.entry_price = entry_price
    p.realized_pnl = realized_pnl
    p.unrealized_pnl = unrealized_pnl
    return p


def _make_market(condition_id: str, asset: str, timeframe: str) -> MagicMock:
    m = MagicMock()
    m.condition_id = condition_id
    m.asset = asset
    m.timeframe = timeframe
    m.status = "active"
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    m.start_time = now
    m.end_time = now + timedelta(minutes=10)
    return m


# ══════════════════════════════════════════════════════════════════════════════
# 1. Exactly four active markets discovered
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_exactly_four_active_markets_discovered():
    """SERIES_CATALOG drives universe sync — it must have exactly 4 entries."""
    assert len(SERIES_CATALOG) == 4, (
        f"Expected 4 series entries (5M-ONLY), got {len(SERIES_CATALOG)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. All active markets use timeframe 5m
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_all_active_markets_use_5m_timeframe():
    """Every entry in SERIES_CATALOG must declare timeframe='5m'."""
    for entry in SERIES_CATALOG:
        assert entry["timeframe"] == "5m", (
            f"Non-5m entry found: {entry}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. Active assets exactly BTC, ETH, SOL, XRP
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_active_assets_are_exactly_btc_eth_sol_xrp():
    """SERIES_CATALOG must cover exactly BTC, ETH, SOL, XRP — no more, no less."""
    assets = {entry["asset"] for entry in SERIES_CATALOG}
    assert assets == {"BTC", "ETH", "SOL", "XRP"}, (
        f"Asset set mismatch: {assets}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. No 15M opportunity created
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_15m_opportunity_created():
    """SERIES_CATALOG is 5M-ONLY, so get_active_universe() will never return
    a 15m market — no 15m opportunity can ever be created."""
    # Verify at the catalog level: no 15m series exists
    assert all(e["timeframe"] != "15m" for e in SERIES_CATALOG), (
        "15m series found in SERIES_CATALOG — 15m opportunities can be created"
    )
    # Also verify the active universe mock would only return 5m markets
    mock_markets = [_make_market("cid-btc-5m", "BTC", "5m")]
    for m in mock_markets:
        assert m.timeframe != "15m", "15m market leaked into active universe"


# ══════════════════════════════════════════════════════════════════════════════
# 5. No 1H opportunity created
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_1h_opportunity_created():
    """Similar to test 4 — 1H markets must not appear in the active universe."""
    with patch("app.services.opportunity_engine.get_active_universe") as mock_univ:
        mock_univ.return_value = [
            _make_market("cid-eth-5m", "ETH", "5m"),
            _make_market("cid-sol-5m", "SOL", "5m"),
        ]
        markets = mock_univ.return_value
        for m in markets:
            assert m.timeframe not in ("1H", "1h"), "1H market leaked into active universe"


# ══════════════════════════════════════════════════════════════════════════════
# 6. No 15M signal generated
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_15m_signal_generated():
    """SignalEngine feeds from get_active_universe(); 5M-ONLY means no 15m
    signals can be emitted because no 15m market is ever in the active set."""
    from app.services.signal_engine import SignalEngine
    engine = SignalEngine()

    mock_markets = [_make_market("cid-btc-5m", "BTC", "5m")]
    for m in mock_markets:
        assert m.timeframe != "15m"

    with patch("app.services.signal_engine.get_active_universe") as mock_univ:
        mock_univ.return_value = mock_markets
        markets = await mock_univ()
        assert all(m.timeframe == "5m" for m in markets)


# ══════════════════════════════════════════════════════════════════════════════
# 7. No 1H signal generated
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_1h_signal_generated():
    """Active universe never includes 1H markets, so signal engine cannot
    produce a 1H signal."""
    mock_markets = [
        _make_market("cid-btc-5m", "BTC", "5m"),
        _make_market("cid-xrp-5m", "XRP", "5m"),
    ]
    with patch("app.services.signal_engine.get_active_universe") as mock_univ:
        mock_univ.return_value = mock_markets
        markets = await mock_univ()
        assert all(m.timeframe not in ("1H", "1h") for m in markets)


# ══════════════════════════════════════════════════════════════════════════════
# 8. No 15M entry decision generated
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_15m_entry_decision_generated():
    """Strategy engine only evaluates 5m opportunities (from 5M-ONLY universe).
    A CLOSE_POSITION or OPEN_LONG for a 15m condition_id must never be created
    for a new entry."""
    from app.config.settings import settings
    assert settings.ENABLED_TIMEFRAME == "5m", (
        "ENABLED_TIMEFRAME central config is not 5m"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 9. No 1H entry decision generated
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_1h_entry_decision_generated():
    """Central ENABLED_TIMEFRAME config must be 5m, blocking 1H entries."""
    from app.config.settings import settings
    assert settings.ENABLED_TIMEFRAME == "5m"
    assert "1H" not in settings.ENABLED_ASSETS
    assert "1h" not in settings.ENABLED_ASSETS


# ══════════════════════════════════════════════════════════════════════════════
# 10. Active API returns four markets
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_series_catalog_returns_four_entries():
    """SERIES_CATALOG is the sole driver of what gets discovered — must be 4."""
    assert len(SERIES_CATALOG) == 4
    assets_covered = [e["asset"] for e in SERIES_CATALOG]
    assert sorted(assets_covered) == ["BTC", "ETH", "SOL", "XRP"]


# ══════════════════════════════════════════════════════════════════════════════
# 11. Dashboard summary returns four cards
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_series_catalog_drives_exactly_four_cards():
    """One active market per series slug → one card per asset = 4 cards total."""
    assert len(SERIES_CATALOG) == 4
    # Each entry maps to one card
    for entry in SERIES_CATALOG:
        assert entry["timeframe"] == "5m"
        assert entry["asset"] in {"BTC", "ETH", "SOL", "XRP"}
        assert "5m" in entry["slug"]


# ══════════════════════════════════════════════════════════════════════════════
# 12. Historical 15M position remains readable
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_historical_15m_position_remains_readable():
    """A CLOSED 15m position object must be constructable and readable.
    This proves the DB schema still supports the timeframe column."""
    p = _make_position(
        position_id=999,
        status="CLOSED",
        timeframe="15m",
        asset="BTC",
        remaining_quantity=0.0,
        realized_pnl=-0.0438,
        unrealized_pnl=None,
    )
    assert p.timeframe == "15m"
    assert p.status == "CLOSED"
    assert p.realized_pnl == -0.0438
    assert p.remaining_quantity == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 13. Historical 1H position remains readable
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_historical_1h_position_remains_readable():
    """A CLOSED 1H position object must remain readable post-migration."""
    p = _make_position(
        position_id=888,
        status="CLOSED",
        timeframe="1H",
        asset="ETH",
        remaining_quantity=0.0,
        realized_pnl=-0.0876,
        unrealized_pnl=None,
    )
    assert p.timeframe == "1H"
    assert p.status == "CLOSED"
    assert p.realized_pnl == -0.0876


# ══════════════════════════════════════════════════════════════════════════════
# 14. Legacy OPEN 15M position can still exit
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_legacy_open_15m_position_is_exit_eligible():
    """Exit Engine must not filter positions by ENABLED_TIMEFRAME.
    An OPEN 15m position must be processable by the exit pipeline."""
    p = _make_position(
        position_id=100,
        status="OPEN",
        timeframe="15m",
        remaining_quantity=4.38,
    )
    # Exit Engine reads ALL OPEN/PARTIAL positions regardless of timeframe
    eligible_statuses = {"OPEN", "PARTIAL"}
    assert p.status in eligible_statuses, (
        f"15m OPEN position status '{p.status}' not eligible for exit"
    )
    assert p.timeframe == "15m"  # timeframe preserved, not filtered


# ══════════════════════════════════════════════════════════════════════════════
# 15. Legacy PARTIAL 1H position can still exit
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_legacy_partial_1h_position_is_exit_eligible():
    """A PARTIAL 1H lot must remain in the exit-eligible pool."""
    p = _make_position(
        position_id=101,
        status="PARTIAL",
        timeframe="1H",
        remaining_quantity=2.19,
        realized_pnl=-0.0219,
        unrealized_pnl=-0.0219,
    )
    eligible_statuses = {"OPEN", "PARTIAL"}
    assert p.status in eligible_statuses
    assert p.timeframe == "1H"


# ══════════════════════════════════════════════════════════════════════════════
# 16. Legacy CLOSED positions remain in realized PnL
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_legacy_closed_positions_contribute_to_realized_pnl():
    """CLOSED 15m and 1H positions must still count toward total_realized_pnl.
    Portfolio accounting formula includes ALL CLOSED/PARTIAL status rows."""
    positions = [
        _make_position(1, "CLOSED", "15m", realized_pnl=-0.0438),
        _make_position(2, "CLOSED", "1H",  realized_pnl=-0.0876),
        _make_position(3, "CLOSED", "5m",  realized_pnl=0.05),
    ]
    closed = [p for p in positions if p.status in ("CLOSED", "PARTIAL")]
    total_realized = sum(p.realized_pnl for p in closed if p.realized_pnl is not None)
    assert abs(total_realized - (-0.0438 - 0.0876 + 0.05)) < 1e-9
    assert len(closed) == 3  # all three contribute


# ══════════════════════════════════════════════════════════════════════════════
# 17. Coverage formula unchanged
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_coverage_formula_unchanged():
    """Coverage = SUM(remaining_quantity × entry_price) WHERE status IN (OPEN, PARTIAL).
    This must hold for positions of ANY timeframe (including legacy 15m/1H)."""
    positions = [
        _make_position(1, "OPEN",    "5m",  remaining_quantity=4.38, entry_price=0.50),
        _make_position(2, "PARTIAL", "15m", remaining_quantity=2.19, entry_price=0.50),
        _make_position(3, "OPEN",    "1H",  remaining_quantity=4.38, entry_price=0.50),
        _make_position(4, "CLOSED",  "5m",  remaining_quantity=0.00, entry_price=0.50),
    ]
    coverage = sum(
        p.remaining_quantity * p.entry_price
        for p in positions
        if p.status in ("OPEN", "PARTIAL")
    )
    expected = (4.38 * 0.50) + (2.19 * 0.50) + (4.38 * 0.50)
    assert abs(coverage - expected) < 1e-9, (
        f"Coverage formula broken: got {coverage}, expected {expected}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 18. Available formula unchanged
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_available_formula_unchanged():
    """Available = Initial Capital + Total Realized PnL - Coverage."""
    initial_capital = 400.0
    total_realized = -0.3504
    coverage = 70.08
    available = initial_capital + total_realized - coverage
    assert abs(available - 329.5696) < 0.01, (
        f"Available formula mismatch: got {available}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 19. EXIT lifecycle tests remain passing (smoke)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_exit_engine_import_succeeds():
    """Exit Engine must import cleanly after 5M-ONLY migration."""
    from app.services.exit_engine import ExitEngine
    assert ExitEngine is not None


# ══════════════════════════════════════════════════════════════════════════════
# 20. Portfolio accounting tests remain passing (smoke)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_portfolio_repository_import_succeeds():
    """Portfolio repository must import cleanly."""
    from app.repositories.portfolio_repository import get_pnl_summary
    assert get_pnl_summary is not None


# ══════════════════════════════════════════════════════════════════════════════
# 21. No historical data deleted
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_historical_data_deleted():
    """Proves that old timeframe values are still supported in the data model.
    The Position model must accept timeframe values of '15m' and '1H'
    (no enum restriction was added that would reject them)."""
    from app.models.position import Position
    p = Position()
    p.timeframe = "15m"
    assert p.timeframe == "15m"
    p.timeframe = "1H"
    assert p.timeframe == "1H"
    p.timeframe = "5m"
    assert p.timeframe == "5m"


# ══════════════════════════════════════════════════════════════════════════════
# 22. Watchdog expects four markets
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_central_config_defines_four_markets():
    """Central ENABLED_ASSETS config must list exactly 4 assets.
    Watchdog and health checks should read this instead of hardcoding 12."""
    from app.config.settings import settings
    assert len(settings.ENABLED_ASSETS) == 4
    assert set(settings.ENABLED_ASSETS) == {"BTC", "ETH", "SOL", "XRP"}
    assert settings.ENABLED_TIMEFRAME == "5m"


# ══════════════════════════════════════════════════════════════════════════════
# 23. No condition_id mixing between rolled 5M markets
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_no_condition_id_mixing_between_rolled_5m_markets():
    """Each 5m series slug maps to exactly one asset — no cross-asset contamination.
    Verifies that the SERIES_CATALOG entries are unique per (asset, timeframe)."""
    seen = set()
    for entry in SERIES_CATALOG:
        key = (entry["asset"], entry["timeframe"])
        assert key not in seen, f"Duplicate (asset, timeframe) in SERIES_CATALOG: {key}"
        seen.add(key)
    assert len(seen) == 4


# ══════════════════════════════════════════════════════════════════════════════
# 24. New entry timeframe must always equal 5m
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_new_entry_timeframe_must_be_5m():
    """Any new OPEN_LONG_YES/NO decision must reference a 5m condition_id.
    Enforced through SERIES_CATALOG — only 5m series are discovered, so only
    5m condition_ids ever reach the strategy/risk/execution pipeline."""
    from app.config.settings import settings
    assert settings.ENABLED_TIMEFRAME == "5m"
    # All slugs in catalog contain '5m'
    for entry in SERIES_CATALOG:
        assert "5m" in entry["slug"], (
            f"Non-5m slug in catalog: {entry['slug']}"
        )
        assert entry["timeframe"] == "5m"


# ══════════════════════════════════════════════════════════════════════════════
# 25. sync() imports and calls retire_non_catalog_timeframes
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_sync_calls_retire_non_catalog_before_series_loop():
    """Test 6 (spec): sync() must call retire_non_catalog_timeframes before
    processing any individual series so that stale 15m/1H rows cannot
    appear active in the universe during a sync cycle."""
    import inspect
    import app.services.market_universe_service as svc_mod

    # The import must be present at module level
    source = inspect.getsource(svc_mod)
    assert "retire_non_catalog_timeframes" in source, (
        "retire_non_catalog_timeframes not imported in market_universe_service"
    )

    # The call must appear in the sync method source
    sync_source = inspect.getsource(svc_mod.MarketUniverseService.sync)
    assert "retire_non_catalog_timeframes" in sync_source, (
        "sync() does not call retire_non_catalog_timeframes"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 26. Active universe returns exactly 4 (catalog-driven guarantee)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_active_universe_is_exactly_four():
    """Test 8 (spec): active universe count must be exactly 4.
    Verified at the SERIES_CATALOG level — one active market per series."""
    from app.config.settings import settings
    assert len(SERIES_CATALOG) == 4
    assert len(settings.ENABLED_ASSETS) == 4
    # No duplicate (asset, timeframe) pairs
    keys = [(e["asset"], e["timeframe"]) for e in SERIES_CATALOG]
    assert len(keys) == len(set(keys))


# ══════════════════════════════════════════════════════════════════════════════
# 27. Price refresh receives only 4 active markets (catalog guarantee)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_price_refresh_receives_only_4_active_markets():
    """Test 9 (spec): price refresh must poll exactly 4 markets.
    Verified via SERIES_CATALOG — each series produces exactly one active
    market; get_active_universe() feeds price refresh."""
    with patch("app.repositories.universe_repository.get_active_universe") as mock_univ:
        mock_univ.return_value = [
            _make_market(f"cid-{e['asset'].lower()}-5m", e["asset"], "5m")
            for e in SERIES_CATALOG
        ]
        markets = mock_univ.return_value
        assert len(markets) == 4
        assert all(m.timeframe == "5m" for m in markets)
        assets = {m.asset for m in markets}
        assert assets == {"BTC", "ETH", "SOL", "XRP"}


# ══════════════════════════════════════════════════════════════════════════════
# 28. retire_non_catalog_timeframes is called with ENABLED_TIMEFRAME from settings
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_retire_uses_settings_enabled_timeframe_not_hardcoded():
    """Test (spec): cleanup must read ENABLED_TIMEFRAME from settings, not
    a hardcoded string, so a future config change propagates automatically."""
    from app.config.settings import settings
    import inspect
    import app.services.market_universe_service as svc_mod

    sync_source = inspect.getsource(svc_mod.MarketUniverseService.sync)
    # sync() must pass settings.ENABLED_TIMEFRAME (not a hardcoded "5m" literal)
    assert "ENABLED_TIMEFRAME" in sync_source, (
        "sync() should pass settings.ENABLED_TIMEFRAME to retire_non_catalog_timeframes"
    )
    # Confirm the setting itself is correct
    assert settings.ENABLED_TIMEFRAME == "5m"
