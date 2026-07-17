"""schemas/portfolio.py — Pydantic response schemas for Layer 10: Portfolio Reporting.

Phase 2 vocabulary migration: serialization aliases expose new terminology in JSON
responses while internal Python field names remain unchanged.
"""

from pydantic import BaseModel, ConfigDict, Field


class AccountingResponse(BaseModel):
    """
    Global accounting snapshot — spec §9 contract.

    Source of truth for all dashboard financial widgets.
    Formula definitions:
      portfolio_active_lots      = COUNT positions WHERE status IN ('OPEN', 'PARTIAL')
      open_exposure              = SUM(remaining_quantity × entry_price) for active lots
      raw_available_capital      = initial_capital + total_realized_pnl - open_exposure
      spendable_available_capital = max(0, raw_available_capital)
      cumulative_outcome          = total_realized_pnl + total_unrealized_pnl
    """
    initial_capital:               float
    portfolio_open_lots:           int
    portfolio_partial_lots:        int
    portfolio_active_lots:         int
    portfolio_active_positions:    int
    open_exposure:                 float
    total_realized_pnl:            float
    total_unrealized_pnl:          float
    raw_available_capital:         float
    spendable_available_capital:   float
    cumulative_outcome:            float
    total_entry_fills:             int
    total_exit_fills:              int


class PortfolioSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Internal names preserved; JSON exposes prediction vocabulary
    total_positions: int = Field(serialization_alias="total_predictions")
    open_positions: int = Field(serialization_alias="active_predictions")
    closed_positions: int = Field(serialization_alias="resolved_predictions")
    total_orders: int
    executed_orders: int
    approved_decisions: int
    blocked_decisions: int
    initial_capital: float


class PositionSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_positions: int = Field(serialization_alias="total_predictions")
    open_positions: int = Field(serialization_alias="active_predictions")
    closed_positions: int = Field(serialization_alias="resolved_predictions")
    by_asset: dict[str, int]
    by_side: dict[str, int]


class OrderSummaryResponse(BaseModel):
    total_orders: int
    filled_orders: int
    pending_orders: int
    by_asset: dict[str, int]
    by_side: dict[str, int]


class RiskSummaryResponse(BaseModel):
    total_checked: int
    allowed: int
    blocked: int
    block_rate_pct: float
    by_reason: dict[str, int]


class PnlSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Position counts → prediction counts
    open_positions: int = Field(serialization_alias="active_predictions")
    closed_positions: int = Field(serialization_alias="resolved_predictions")

    # PnL vocabulary → prediction outcome vocabulary
    total_unrealized_pnl: float = Field(serialization_alias="total_live_state")
    average_unrealized_pnl: float = Field(serialization_alias="average_live_state")
    total_realized_pnl: float = Field(serialization_alias="total_resolution_result")
