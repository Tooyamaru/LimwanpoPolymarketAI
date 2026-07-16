"""
ConfidenceCalibrationService — Priority 3 & 6: Confidence Calibration +
Confidence-vs-Performance Buckets.

Recomputes, from all outcome_learnings rows with a known confidence and
correctness, a set of 5%-wide confidence buckets (50-55, 55-60, ... 95-100,
plus a catch-all "below 50" bucket) and a global calibration summary:

  ACE (Average Calibration Error) — unweighted mean of per-bucket
      |accuracy - avg_confidence|.
  ECE (Expected Calibration Error) — sample-count-weighted mean of the
      same per-bucket errors (standard ECE definition).
  overconfident_pct / underconfident_pct / well_calibrated_pct — reuse the
      existing per-row `confidence_calibration` classification already
      computed by OutcomeLearningService, aggregated as percentages.

Runs after every OutcomeLearningService batch, alongside EnginePerformanceService.

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import confidence_calibration_repository as cal_repo
from app.repositories import outcome_learning_repository as ol_repo

logger = get_logger(__name__)

# 5%-wide buckets from 50 to 100
_BUCKET_EDGES = [50.0 + 5.0 * i for i in range(11)]  # 50, 55, ..., 100
_BELOW_50_MIN = 0.0
_BELOW_50_MAX = 50.0


class ConfidenceCalibrationService:
    """
    Priority 3 & 6 — Confidence Calibration + Confidence-vs-Performance Buckets.

    Usage::

        svc = ConfidenceCalibrationService()
        result = await svc.recompute(session)
    """

    async def recompute(self, session: AsyncSession) -> dict:
        outcomes = await ol_repo.get_all_outcomes(session)

        # Only rows with both a confidence value and a known correctness flag
        usable = [o for o in outcomes if o.confidence is not None and o.correct is not None]

        if not usable:
            logger.debug("Confidence calibration: no usable outcomes yet")
            return {}

        # Build bucket rows: below-50 catch-all + ten 5%-wide buckets 50-100
        buckets: list[tuple[float, float]] = [(_BELOW_50_MIN, _BELOW_50_MAX)]
        for i in range(len(_BUCKET_EDGES) - 1):
            buckets.append((_BUCKET_EDGES[i], _BUCKET_EDGES[i + 1]))

        bucket_errors: list[tuple[float, float]] = []  # (calibration_error, sample_count) for ACE/ECE
        total_with_result = len(usable)

        for bucket_min, bucket_max in buckets:
            if bucket_max <= 50.0:
                rows = [o for o in usable if o.confidence < 50.0]
            else:
                rows = [
                    o for o in usable
                    if bucket_min <= o.confidence < bucket_max
                    or (bucket_max == 100.0 and o.confidence == 100.0)
                ]

            sample_count = len(rows)
            if sample_count == 0:
                await cal_repo.upsert_bucket(
                    session,
                    bucket_min=bucket_min,
                    bucket_max=bucket_max,
                    sample_count=0,
                    correct_count=0,
                    accuracy=None,
                    avg_confidence=None,
                    calibration_error=None,
                    avg_pnl=None,
                    win_rate=None,
                )
                continue

            correct_count = sum(1 for o in rows if o.correct is True)
            accuracy = round(correct_count / sample_count * 100.0, 2)
            avg_confidence = round(sum(o.confidence for o in rows) / sample_count, 2)
            calibration_error = round(abs(accuracy - avg_confidence), 2)

            pnl_vals = [o.actual_pnl for o in rows if o.actual_pnl is not None]
            avg_pnl = round(sum(pnl_vals) / len(pnl_vals), 6) if pnl_vals else None

            win_count = sum(1 for o in rows if (o.actual_pnl or 0) > 0)
            win_rate = round(win_count / sample_count * 100.0, 2)

            await cal_repo.upsert_bucket(
                session,
                bucket_min=bucket_min,
                bucket_max=bucket_max,
                sample_count=sample_count,
                correct_count=correct_count,
                accuracy=accuracy,
                avg_confidence=avg_confidence,
                calibration_error=calibration_error,
                avg_pnl=avg_pnl,
                win_rate=win_rate,
            )
            bucket_errors.append((calibration_error, sample_count))

        # ACE — unweighted mean across non-empty buckets
        ace: Optional[float] = (
            round(sum(err for err, _ in bucket_errors) / len(bucket_errors), 4)
            if bucket_errors else None
        )
        # ECE — sample-weighted mean across non-empty buckets
        total_samples = sum(n for _, n in bucket_errors)
        ece: Optional[float] = (
            round(sum(err * n for err, n in bucket_errors) / total_samples, 4)
            if total_samples > 0 else None
        )

        # Over/under/well-calibrated percentages reuse the per-row classification
        with_calibration = [
            o for o in outcomes if o.confidence_calibration in
            ("OVERCONFIDENT", "UNDERCONFIDENT", "WELL_CALIBRATED")
        ]
        total_calib = len(with_calibration)
        overconfident_pct = (
            round(sum(1 for o in with_calibration if o.confidence_calibration == "OVERCONFIDENT")
                  / total_calib * 100.0, 2)
            if total_calib > 0 else None
        )
        underconfident_pct = (
            round(sum(1 for o in with_calibration if o.confidence_calibration == "UNDERCONFIDENT")
                  / total_calib * 100.0, 2)
            if total_calib > 0 else None
        )
        well_calibrated_pct = (
            round(sum(1 for o in with_calibration if o.confidence_calibration == "WELL_CALIBRATED")
                  / total_calib * 100.0, 2)
            if total_calib > 0 else None
        )

        await cal_repo.upsert_summary(
            session,
            ace=ace,
            ece=ece,
            overconfident_pct=overconfident_pct,
            underconfident_pct=underconfident_pct,
            well_calibrated_pct=well_calibrated_pct,
            total_evaluated=total_with_result,
        )

        logger.info(
            "Confidence calibration recomputed",
            ace=ace,
            ece=ece,
            total_evaluated=total_with_result,
        )
        return {
            "ace": ace,
            "ece": ece,
            "overconfident_pct": overconfident_pct,
            "underconfident_pct": underconfident_pct,
            "well_calibrated_pct": well_calibrated_pct,
            "total_evaluated": total_with_result,
        }
