---
name: Portfolio Priority Score (Priority 8)
description: Priority 8 implementation details for portfolio_allocation_service.py priority_score field
---

Priority 8 adds `priority_score: Optional[float]` to `AllocationDecision` dataclass and computes it alongside `allocation_score` in `allocate()`.

**Formula (0-100):**
```
priority_score = (
  ai_score      × PW_AI_SCORE        (0.20)
  + confidence  × PW_CONFIDENCE      (0.15)
  + risk_proxy  × PW_RISK            (0.15)  # entry_quality_score as proxy
  + opp_score   × PW_EXPECTED_VALUE  (0.15)  # opportunity_score as expected value proxy
  + spread_tight × PW_SPREAD         (0.10)
  + liq_score   × PW_LIQUIDITY       (0.10)  # from latest MarketPriceSnapshot
  + hist_edge   × PW_HISTORICAL_EDGE (0.10)  # from MarketTypePerformance accuracy
  + ew_signal   × PW_ENGINE_WEIGHT   (0.05)  # from EngineWeight current/base ratio
)
```

**Key implementation note:** `scored` list changed from `list[tuple[float, Opportunity]]` to `list[tuple[float, Opportunity, Optional[float]]]`. The loop that unpacks scored must use `for score, opp, p_score in scored:`.

**Why:** Priority 8 needed a richer ranking signal than allocation_score alone. The 8 components cover signal quality, market tradability, and AI system performance.

**How to apply:** priority_score does NOT replace allocation_score or the ENTER/DEFER/SKIP gates. It is additive context returned in `_to_dict()` for external consumers.
