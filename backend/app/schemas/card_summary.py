"""
schemas/card_summary.py — Pydantic response schema for the market-card
PNL / IN / OUT aggregation endpoint.

Backs GET /positions/card-summary — one row per active condition_id.
Markets with no positions return zero-filled rows with has_position=False
and total_pnl=None so the frontend can distinguish "no position" from
"position with $0 PnL".

Sprint 12F+: Now includes live market price fields and side-split exposure
per spec §10 API contract.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CardSummaryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition_id: str
    asset: Optional[str] = None
    timeframe: Optional[str] = None

    # ── Market price (sourced from latest CLOB snapshot) ──────────────────────
    # UP = YES token, DOWN = NO token.
    # market_data_stale=True means the snapshot exceeds 2× PRICE_REFRESH_SECONDS.
    market_updated_at: Optional[datetime] = None
    market_data_stale: bool = True
    up_bid:   Optional[float] = None
    up_ask:   Optional[float] = None
    up_mark:  Optional[float] = None   # (up_bid + up_ask) / 2
    down_bid: Optional[float] = None
    down_ask: Optional[float] = None
    down_mark: Optional[float] = None  # (down_bid + down_ask) / 2

    # ── Whether any position (lot) exists for this condition_id ───────────────
    has_position: bool = False

    # ── Active lots: OPEN + PARTIAL only (excludes CLOSED) ───────────────────
    open_lot_count:    int = 0
    partial_lot_count: int = 0
    closed_lot_count:  int = 0
    total_lot_count:   int = 0
    active_lot_count:  int = 0   # open_lot_count + partial_lot_count

    # ── Side-split exposure (spec §10) ────────────────────────────────────────
    # up_open_exposure   = SUM(remaining_qty × entry_price) WHERE side=LONG_YES
    # down_open_exposure = SUM(remaining_qty × entry_price) WHERE side=LONG_NO
    up_open_exposure:   float = 0.0
    down_open_exposure: float = 0.0
    open_exposure_usdc: float = 0.0   # legacy combined (up + down)

    # active_side: which side(s) have open exposure  NONE|YES|NO|MIXED
    active_side:  str = "NONE"
    current_side: str = "NONE"  # legacy alias

    # ── IN — executed entry fills (spec §10 names + legacy names) ─────────────
    entry_fill_count: int = 0          # spec §10
    entry_notional:   float = 0.0     # spec §10
    total_entry_count:          int   = 0    # legacy
    total_entry_notional_usdc:  float = 0.0  # legacy

    # ── OUT — executed exit fills (spec §10 names + legacy names) ─────────────
    exit_fill_count: int = 0           # spec §10
    exit_proceeds:   float = 0.0      # spec §10
    total_exit_count:          int   = 0    # legacy
    total_exit_notional_usdc:  float = 0.0  # legacy

    # ── Quantity / price summary (spec §10 names + legacy names) ──────────────
    open_shares:   float = 0.0           # spec §10 — SUM(remaining_quantity)
    remaining_quantity: float = 0.0      # legacy alias
    average_entry: Optional[float] = None           # spec §10 — weighted avg
    weighted_average_entry_price: Optional[float] = None  # legacy alias

    # ── PnL ───────────────────────────────────────────────────────────────────
    # unrealized_pnl is computed fresh from executable bid prices when a
    # snapshot is available; falls back to stored position value otherwise.
    realized_pnl:   float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: Optional[float] = None  # null = no position; 0.0 = real breakeven

    # ── Timestamps ───────────────────────────────────────────────────────────
    latest_entry_at: Optional[datetime] = None
    latest_exit_at:  Optional[datetime] = None
