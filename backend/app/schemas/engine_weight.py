"""Schemas — Engine Weights (Priority 3)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.config.settings import settings


class EngineWeightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    engine_name: str
    base_weight: float
    current_weight: float
    min_weight: float
    max_weight: float
    adjustment_factor: Optional[float]
    outcomes_evaluated: int
    accuracy_at_adjustment: Optional[float]
    last_adjusted_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def status(self) -> str:
        """
        AI Decision Integrity — DEFAULT vs LEARNED must never be ambiguous.

        - INSUFFICIENT_HISTORY: fewer outcomes than DYNAMIC_WEIGHT_MIN_OUTCOMES
          have been evaluated. `current_weight` is the hardcoded base_weight —
          it is NOT learned evidence, even though the number looks "computed".
        - LEARNED: enough outcomes exist and the weight has actually been
          adjusted away from base by real historical performance.
        - DEFAULT: enough outcomes exist but performance kept the weight
          pinned at (or within rounding of) its base value.
        - NOT_AVAILABLE: enough outcomes exist but accuracy could not be
          computed (defensive edge case) — base weight kept, never coerced
          to a fabricated 50% accuracy read.
        """
        if self.outcomes_evaluated < settings.DYNAMIC_WEIGHT_MIN_OUTCOMES:
            return "INSUFFICIENT_HISTORY"
        if self.accuracy_at_adjustment is None:
            return "NOT_AVAILABLE"
        if self.adjustment_factor is not None and abs(self.adjustment_factor) > 0.001:
            return "LEARNED"
        return "DEFAULT"


class EngineWeightSummaryResponse(BaseModel):
    total_engines: int
    engines_adjusted: int
    engines_at_base: int
    engines: list[EngineWeightResponse]
