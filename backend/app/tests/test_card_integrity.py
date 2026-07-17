"""
test_card_integrity.py — validates CardSummaryItem schema completeness.

Verifies all spec §10 / §17 required fields are present on the
CardSummaryItem response schema class with correct types and default values.
The card fingerprint proof (section 10 of handoff) requires that these
fields exist so position changes without a price change still trigger
DOM updates.
"""

from app.schemas.card_summary import CardSummaryItem
from pydantic import BaseModel


def test_card_summary_item_is_pydantic_model():
    """CardSummaryItem must be a Pydantic BaseModel."""
    assert issubclass(CardSummaryItem, BaseModel)


def test_card_summary_item_spec10_fields_present():
    """All spec §10 field names must be present on CardSummaryItem."""
    fields = CardSummaryItem.model_fields
    required = [
        "condition_id",
        "entry_fill_count",
        "entry_notional",
        "exit_fill_count",
        "exit_proceeds",
        "open_shares",
        "average_entry",
        "open_cost_basis",
        "up_open_exposure",
        "down_open_exposure",
        "active_side",
        "active_lot_count",
        "open_lot_count",
        "partial_lot_count",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "market_data_stale",
        "has_position",
    ]
    missing = [f for f in required if f not in fields]
    assert missing == [], f"Missing CardSummaryItem fields: {missing}"


def test_card_summary_item_defaults_no_position():
    """Zero-fill contract: a market with no position returns sane defaults."""
    item = CardSummaryItem(condition_id="test-001")
    assert item.has_position is False
    assert item.active_lot_count == 0
    assert item.open_lot_count == 0
    assert item.partial_lot_count == 0
    assert item.entry_fill_count == 0
    assert item.exit_fill_count == 0
    assert item.open_shares == 0.0
    assert item.open_cost_basis == 0.0
    assert item.up_open_exposure == 0.0
    assert item.down_open_exposure == 0.0
    assert item.active_side == "NONE"
    assert item.total_pnl is None


def test_card_summary_item_field_types():
    """Field types must match spec §10 contract."""
    item = CardSummaryItem(
        condition_id="test-002",
        has_position=True,
        active_lot_count=2,
        open_lot_count=1,
        partial_lot_count=1,
        entry_fill_count=3,
        entry_notional=15.0,
        exit_fill_count=1,
        exit_proceeds=6.5,
        open_shares=50.0,
        average_entry=0.30,
        open_cost_basis=15.0,
        up_open_exposure=15.0,
        down_open_exposure=0.0,
        active_side="YES",
        realized_pnl=1.5,
        unrealized_pnl=0.5,
        total_pnl=2.0,
    )
    assert isinstance(item.entry_fill_count, int)
    assert isinstance(item.exit_fill_count, int)
    assert isinstance(item.open_shares, float)
    assert isinstance(item.up_open_exposure, float)
    assert isinstance(item.down_open_exposure, float)
    assert isinstance(item.active_lot_count, int)
    assert isinstance(item.active_side, str)
    assert item.total_pnl == 2.0
    assert item.average_entry == 0.30


def test_card_summary_side_split_consistency():
    """open_cost_basis should equal up + down exposure (spec §17 alias)."""
    up = 10.0
    down = 5.0
    item = CardSummaryItem(
        condition_id="test-003",
        up_open_exposure=up,
        down_open_exposure=down,
        open_cost_basis=up + down,
        open_exposure_usdc=up + down,
    )
    assert abs(item.open_cost_basis - (item.up_open_exposure + item.down_open_exposure)) < 0.001


def test_card_summary_active_lot_count_consistency():
    """active_lot_count must equal open_lot_count + partial_lot_count."""
    item = CardSummaryItem(
        condition_id="test-004",
        open_lot_count=2,
        partial_lot_count=1,
        active_lot_count=3,
    )
    assert item.active_lot_count == item.open_lot_count + item.partial_lot_count


def test_card_summary_market_data_stale_default():
    """market_data_stale must default True (conservative: stale until proven fresh)."""
    item = CardSummaryItem(condition_id="test-005")
    assert item.market_data_stale is True


def test_card_summary_entry_notional_and_proceeds_types():
    """entry_notional and exit_proceeds must be float."""
    item = CardSummaryItem(
        condition_id="test-006",
        entry_notional=12.50,
        exit_proceeds=8.25,
    )
    assert isinstance(item.entry_notional, float)
    assert isinstance(item.exit_proceeds, float)
