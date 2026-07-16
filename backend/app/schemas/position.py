"""schemas/position.py — Pydantic response schemas for Layer 8: Position Tracking.

Phase 2 vocabulary migration: serialization aliases expose new terminology in JSON
responses while internal Python field names and DB columns remain unchanged.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    order_id: int
    condition_id: str
    asset: str
    timeframe: str
    side: str
    quantity: float
    remaining_quantity: Optional[float] = None

    # Entry price → open_price in JSON
    entry_price: float = Field(serialization_alias="open_price")
    current_price: Optional[float] = None

    # PnL fields → prediction outcome vocabulary in JSON
    unrealized_pnl: Optional[float] = Field(default=None, serialization_alias="live_state")
    realized_pnl: Optional[float] = Field(default=None, serialization_alias="resolution_result")

    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None

    # Layer 12: exit audit trail
    close_reason: Optional[str] = None
    exit_price: Optional[float] = Field(default=None, serialization_alias="resolution_price")
    close_decision_id: Optional[int] = None
    close_order_id: Optional[int] = None

    @computed_field
    @property
    def allocation(self) -> float:
        """Current open exposure for this lot = remaining_quantity × entry_price.

        Uses remaining_quantity (not original quantity) so partial exits correctly
        reduce the reported exposure. Falls back to original quantity for positions
        that pre-date the remaining_quantity column.
        """
        qty = self.remaining_quantity if self.remaining_quantity is not None else self.quantity
        return qty * self.entry_price


class PositionStatsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_positions: int = Field(serialization_alias="total_predictions")
    open: int
    closed: int
    total_unrealized_pnl: float = Field(serialization_alias="total_live_state")
    total_realized_pnl: float = Field(serialization_alias="total_resolution_result")
    avg_unrealized_pnl: float = Field(serialization_alias="avg_live_state")
