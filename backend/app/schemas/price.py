"""
Price snapshot response schemas — Layer 3b: Price Refresh / Sprint 9.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PriceSnapshotResponse(BaseModel):
    id: int
    condition_id: str
    yes_token_id: Optional[str]
    no_token_id: Optional[str]

    yes_bid: Optional[float]
    yes_ask: Optional[float]
    yes_mid: Optional[float]

    no_bid: Optional[float]
    no_ask: Optional[float]
    no_mid: Optional[float]

    spread_yes: Optional[float]
    spread_no: Optional[float]

    volume: Optional[float]
    liquidity: Optional[float]

    captured_at: datetime

    asset: Optional[str] = None
    timeframe: Optional[str] = None

    # ── Trading activity classification (computed at API layer) ──────────────────
    # trading_activity_state: one of
    #   ACTIVE_WITH_ORDER_FLOW  — volume > 0; real human trades confirmed
    #   ACTIVE_SEED_ONLY        — volume null/0; book at AMM init levels only
    #   ACTIVE_STALE_BOOK       — snapshot older than 2x price-refresh interval
    #   ACTIVE_DATA_MISSING     — no snapshot exists for this market
    trading_activity_state: str = "ACTIVE_DATA_MISSING"
    # has_order_flow: True when volume > 0 (confirmed human trades)
    has_order_flow: bool = False
    # has_recent_trade: alias for has_order_flow (volume proxy; no trade-tick data yet)
    has_recent_trade: bool = False
    # orderbook_fresh: True when captured_at < 2 × PRICE_REFRESH_SECONDS ago
    orderbook_fresh: bool = False
    # price_data_mode: summary tag for frontend/dashboard labeling
    #   SEED          — AMM seed book only (volume null or 0)
    #   LIVE_ORDER_FLOW — real trades/volume confirmed
    #   STALE         — snapshot too old
    #   MISSING       — no snapshot
    price_data_mode: str = "MISSING"

    model_config = {"from_attributes": True}


class PriceStatsResponse(BaseModel):
    total_snapshots: int
    active_markets_with_data: int
    assets_covered: list[str]
    timeframes_covered: list[str]
