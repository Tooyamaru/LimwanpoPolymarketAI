"""
schemas/card_summary.py — Pydantic response schema for the market-card
PNL / IN / OUT aggregation endpoint.

Backs GET /positions/card-summary — one row per active condition_id.
Markets with no positions return zero-filled rows with has_position=False
and total_pnl=None so the frontend can distinguish "no position" from
"position with $0 PnL".
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CardSummaryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition_id: str
    asset: Optional[str] = None
    timeframe: Optional[str] = None

    # Whether any position (lot) exists for this condition_id
    has_position: bool = False

    # Active lots: OPEN + PARTIAL only (excludes CLOSED)
    open_lot_count: int = 0
    partial_lot_count: int = 0
    closed_lot_count: int = 0
    total_lot_count: int = 0
    active_lot_count: int = 0          # open_lot_count + partial_lot_count

    # IN — executed entry fills (OPEN_LONG_YES / OPEN_LONG_NO), one per lot
    total_entry_count: int = 0
    total_entry_notional_usdc: float = 0.0

    # OUT — executed exit fills (SELL_YES / SELL_NO); partial exits each
    # contribute one OUT event
    total_exit_count: int = 0
    total_exit_notional_usdc: float = 0.0

    # Current exposure — sum(remaining_quantity) / sum(remaining_qty * entry_price)
    # across lots that are still OPEN or PARTIAL
    remaining_quantity: float = 0.0
    open_exposure_usdc: float = 0.0
    weighted_average_entry_price: Optional[float] = None

    # PnL — real, derived from Position rows only (never a fake preview).
    # None when has_position=False; $0.00 is a real result.
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: Optional[float] = None  # null = no position; 0.0 = real breakeven

    # NONE | YES | NO | MIXED
    current_side: str = "NONE"

    latest_entry_at: Optional[datetime] = None
    latest_exit_at: Optional[datetime] = None
