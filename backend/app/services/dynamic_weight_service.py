"""
DynamicWeightService — Priority 3: Dynamic Engine Weight.

Reads EnginePerformance stats and computes adjusted weights for each engine.
Weights are written to engine_weights table and read by DecisionEngine.

Formula:
  accuracy_fraction = accuracy / 100   (0.0 – 1.0)
  adjustment = (accuracy_fraction - 0.5) * 2.0   (-1.0 to +1.0)
  new_weight = base_weight * (1 + adjustment * ADJUSTMENT_SCALE)
  new_weight = clamp(new_weight, min_weight, max_weight)

Rule: only adjust if engine has ≥ MIN_OUTCOMES evaluated outcomes.
Rule: sum of all weights is NOT renormalised — each weight is independent.

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.engine_weight import BASE_WEIGHTS, WEIGHT_MAX, WEIGHT_MIN
from app.repositories import confidence_calibration_repository as cal_repo
from app.repositories import engine_performance_repository as ep_repo
from app.repositories import engine_weight_repository as ew_repo
from app.repositories import market_type_performance_repository as mtp_repo
from app.repositories import outcome_learning_repository as ol_repo
from app.services.engine_performance_service import ENGINE_DIRECTION_MAP, _engine_was_correct

logger = get_logger(__name__)

# How aggressively to adjust weights (30% swing from base at 100% or 0% accuracy)
ADJUSTMENT_SCALE = 0.30

# ── Priority 7: Smart Dynamic Engine Weight ──────────────────────────────────
# Blend of historical accuracy, recency, contribution, calibration, stability,
# and market-type performance, each contributing a term in [-1, +1].
RECENCY_WINDOW = 30          # most recent N outcomes considered per engine
RECENCY_DECAY = 0.9          # exponential decay per step back in time
SMART_ADJUSTMENT_SCALE = 0.35

W_HISTORICAL   = 0.40
W_RECENCY      = 0.25
W_CONTRIBUTION = 0.15
W_STABILITY    = 0.10
W_CALIBRATION  = 0.05
W_MARKET_TYPE  = 0.05


def _term(metric_pct: Optional[float], default_pct: float = 50.0) -> float:
    """Map a 0-100 metric to a [-1, +1] term centred on 50."""
    value = metric_pct if metric_pct is not None else default_pct
    return (value / 100.0 - 0.5) * 2.0


def _compute_new_weight(
    engine_name: str,
    accuracy: float,
    total_evaluated: int,
) -> tuple[float, float]:
    """
    Compute new weight and adjustment factor.
    Returns (new_weight, adjustment_factor).
    """
    base   = BASE_WEIGHTS.get(engine_name, 0.10)
    w_min  = WEIGHT_MIN.get(engine_name, 0.01)
    w_max  = WEIGHT_MAX.get(engine_name, 1.0)

    accuracy_fraction = accuracy / 100.0
    adjustment        = (accuracy_fraction - 0.5) * 2.0  # -1.0 to +1.0
    new_weight        = base * (1.0 + adjustment * ADJUSTMENT_SCALE)
    new_weight        = max(w_min, min(w_max, new_weight))

    return round(new_weight, 4), round(adjustment, 4)


def _recency_and_stability(
    engine_name: str, outcomes_desc: list,
) -> tuple[Optional[float], Optional[float], int]:
    """
    Priority 7 — per-engine recency accuracy (exponentially decayed, most
    recent outcomes weighted highest) and stability (100 - stdev of a
    rolling correctness signal, i.e. how consistent the engine has been).

    `outcomes_desc` must already be ordered most-recent-first.
    Returns (recency_accuracy_pct, stability_score_pct, sample_n).
    """
    window = outcomes_desc[:RECENCY_WINDOW]
    signals: list[float] = []
    for outcome in window:
        result = _engine_was_correct(engine_name, outcome)
        if result is not None:
            signals.append(1.0 if result else 0.0)

    if not signals:
        return None, None, 0

    weights = [RECENCY_DECAY ** i for i in range(len(signals))]
    weighted_sum = sum(s * w for s, w in zip(signals, weights))
    weight_total = sum(weights)
    recency_accuracy = round(weighted_sum / weight_total * 100.0, 2)

    if len(signals) >= 2:
        mean = sum(signals) / len(signals)
        variance = sum((s - mean) ** 2 for s in signals) / len(signals)
        stdev = variance ** 0.5
        stability_score = round(max(0.0, 100.0 - stdev * 200.0), 2)
    else:
        stability_score = None

    return recency_accuracy, stability_score, len(signals)


class DynamicWeightService:
    """
    Priority 3 — Dynamic Engine Weight.

    Usage::

        svc = DynamicWeightService()
        result = await svc.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        min_outcomes = settings.DYNAMIC_WEIGHT_MIN_OUTCOMES
        started = datetime.now(timezone.utc)

        # Load all engine performance stats
        performances = await ep_repo.get_all_engine_performances(session)

        if not performances:
            logger.info("Dynamic weights: no engine performance data yet — using base weights")
            # Write base weights as defaults so table is populated
            for engine_name, base_w in BASE_WEIGHTS.items():
                await ew_repo.upsert_engine_weight(
                    session,
                    engine_name=engine_name,
                    current_weight=base_w,
                    adjustment_factor=0.0,
                    outcomes_evaluated=0,
                    accuracy_at_adjustment=None,
                )
            await session.commit()
            return {"adjusted": 0, "seeded": len(BASE_WEIGHTS)}

        adjusted    = 0
        kept_base   = 0
        adjustments = {}

        perf_by_name = {p.engine_name: p for p in performances}

        # Priority 7: global context shared across all engines — the
        # calibration summary and average market-type accuracy don't vary
        # per engine, only per-engine historical/recency/contribution/
        # stability terms do.
        outcomes_desc = sorted(
            await ol_repo.get_all_outcomes(session),
            key=lambda o: o.evaluated_at,
            reverse=True,
        )
        calibration_summary = await cal_repo.get_summary(session)
        global_calibration_pct = (
            calibration_summary.well_calibrated_pct
            if calibration_summary is not None else None
        )
        market_type_rows = await mtp_repo.get_all(session)
        market_type_accuracies = [
            r.accuracy for r in market_type_rows if r.accuracy is not None
        ]
        global_market_type_pct = (
            round(sum(market_type_accuracies) / len(market_type_accuracies), 2)
            if market_type_accuracies else None
        )

        for engine_name in BASE_WEIGHTS:
            perf = perf_by_name.get(engine_name)

            if perf is None or perf.total_evaluated < min_outcomes:
                # Not enough data — keep base weight
                base_w = BASE_WEIGHTS[engine_name]
                await ew_repo.upsert_engine_weight(
                    session,
                    engine_name=engine_name,
                    current_weight=base_w,
                    adjustment_factor=0.0,
                    outcomes_evaluated=perf.total_evaluated if perf else 0,
                    accuracy_at_adjustment=perf.accuracy if perf else None,
                    recency_accuracy=None,
                    stability_score=None,
                    factor_breakdown=None,
                )
                kept_base += 1
                adjustments[engine_name] = {
                    "weight": base_w,
                    "status": "BASE_NOT_ENOUGH_DATA",
                    "outcomes": perf.total_evaluated if perf else 0,
                }
                continue

            if perf.accuracy is None:
                # Phase 9B: perf.total_evaluated >= min_outcomes but accuracy
                # is still None (defensive edge case — should not occur given
                # how EnginePerformanceService computes accuracy, but must
                # never be silently coerced to 50.0 and treated as a real
                # historical read). Keep base weight, mark explicitly.
                base_w = BASE_WEIGHTS[engine_name]
                await ew_repo.upsert_engine_weight(
                    session,
                    engine_name=engine_name,
                    current_weight=base_w,
                    adjustment_factor=0.0,
                    outcomes_evaluated=perf.total_evaluated,
                    accuracy_at_adjustment=None,
                    recency_accuracy=None,
                    stability_score=None,
                    factor_breakdown=None,
                )
                kept_base += 1
                adjustments[engine_name] = {
                    "weight": base_w,
                    "status": "NOT_AVAILABLE",
                    "outcomes": perf.total_evaluated,
                }
                logger.warning(
                    "Dynamic weight: accuracy is None despite enough outcomes — "
                    "keeping base weight instead of defaulting to 50.0",
                    engine_name=engine_name,
                    outcomes_evaluated=perf.total_evaluated,
                )
                continue

            accuracy = perf.accuracy

            # Priority 7 — smart blended adjustment replaces the simple
            # accuracy-only adjustment once an engine has enough history.
            recency_accuracy, stability_score, recency_n = _recency_and_stability(
                engine_name, outcomes_desc
            )
            recency_shrink = min(1.0, recency_n / 10.0) if recency_n else 0.0

            contribution_term = (
                _term(perf.contribution_pct) * W_CONTRIBUTION
                if perf.contribution_pct is not None else 0.0
            )
            terms = {
                "historical":   _term(accuracy) * W_HISTORICAL,
                "recency":      _term(recency_accuracy, accuracy) * W_RECENCY * recency_shrink,
                "contribution": contribution_term,
                "stability":    _term(stability_score, 70.0) * W_STABILITY,
                "calibration":  _term(global_calibration_pct, 60.0) * W_CALIBRATION,
                "market_type":  _term(global_market_type_pct, 50.0) * W_MARKET_TYPE,
            }
            smart_adjustment = sum(terms.values())

            base = BASE_WEIGHTS[engine_name]
            w_min = WEIGHT_MIN.get(engine_name, 0.01)
            w_max = WEIGHT_MAX.get(engine_name, 1.0)
            new_weight = base * (1.0 + smart_adjustment * SMART_ADJUSTMENT_SCALE)
            new_weight = round(max(w_min, min(w_max, new_weight)), 4)
            factor = round(smart_adjustment, 4)

            factor_breakdown = json.dumps({
                "terms": {k: round(v, 4) for k, v in terms.items()},
                "recency_n": recency_n,
                "recency_shrink": round(recency_shrink, 2),
            })

            await ew_repo.upsert_engine_weight(
                session,
                engine_name=engine_name,
                current_weight=new_weight,
                adjustment_factor=factor,
                outcomes_evaluated=perf.total_evaluated,
                accuracy_at_adjustment=accuracy,
                recency_accuracy=recency_accuracy,
                stability_score=stability_score,
                factor_breakdown=factor_breakdown,
            )
            adjusted += 1
            adjustments[engine_name] = {
                "weight":   new_weight,
                "base":     BASE_WEIGHTS[engine_name],
                "accuracy": accuracy,
                "factor":   factor,
                "status":   "ADJUSTED",
                "outcomes": perf.total_evaluated,
                "recency_accuracy": recency_accuracy,
                "stability_score": stability_score,
            }

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Dynamic weights updated",
            adjusted=adjusted,
            kept_base=kept_base,
            min_outcomes=min_outcomes,
            duration_ms=elapsed_ms,
            weights={k: v["weight"] for k, v in adjustments.items()},
        )
        return {
            "adjusted":    adjusted,
            "kept_base":   kept_base,
            "duration_ms": elapsed_ms,
            "engines":     adjustments,
        }
