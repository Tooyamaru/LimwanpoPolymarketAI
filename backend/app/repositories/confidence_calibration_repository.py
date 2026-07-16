"""confidence_calibration_repository.py — Priority 3 & 6 persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.confidence_calibration import CalibrationSummary, ConfidenceBucketStat

logger = get_logger(__name__)

_SUMMARY_ROW_ID = 1


async def upsert_bucket(
    session: AsyncSession,
    *,
    bucket_min: float,
    bucket_max: float,
    sample_count: int,
    correct_count: int,
    accuracy: Optional[float],
    avg_confidence: Optional[float],
    calibration_error: Optional[float],
    avg_pnl: Optional[float],
    win_rate: Optional[float],
) -> ConfidenceBucketStat:
    stmt = (
        pg_insert(ConfidenceBucketStat)
        .values(
            bucket_min=bucket_min,
            bucket_max=bucket_max,
            sample_count=sample_count,
            correct_count=correct_count,
            accuracy=accuracy,
            avg_confidence=avg_confidence,
            calibration_error=calibration_error,
            avg_pnl=avg_pnl,
            win_rate=win_rate,
            computed_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["bucket_min"],
            set_={
                "bucket_max": bucket_max,
                "sample_count": sample_count,
                "correct_count": correct_count,
                "accuracy": accuracy,
                "avg_confidence": avg_confidence,
                "calibration_error": calibration_error,
                "avg_pnl": avg_pnl,
                "win_rate": win_rate,
                "computed_at": datetime.now(timezone.utc),
            },
        )
        .returning(ConfidenceBucketStat)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all_buckets(session: AsyncSession) -> list[ConfidenceBucketStat]:
    result = await session.execute(
        select(ConfidenceBucketStat).order_by(ConfidenceBucketStat.bucket_min)
    )
    return list(result.scalars().all())


async def upsert_summary(
    session: AsyncSession,
    *,
    ace: Optional[float],
    ece: Optional[float],
    overconfident_pct: Optional[float],
    underconfident_pct: Optional[float],
    well_calibrated_pct: Optional[float],
    total_evaluated: int,
) -> CalibrationSummary:
    stmt = (
        pg_insert(CalibrationSummary)
        .values(
            id=_SUMMARY_ROW_ID,
            ace=ace,
            ece=ece,
            overconfident_pct=overconfident_pct,
            underconfident_pct=underconfident_pct,
            well_calibrated_pct=well_calibrated_pct,
            total_evaluated=total_evaluated,
            computed_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "ace": ace,
                "ece": ece,
                "overconfident_pct": overconfident_pct,
                "underconfident_pct": underconfident_pct,
                "well_calibrated_pct": well_calibrated_pct,
                "total_evaluated": total_evaluated,
                "computed_at": datetime.now(timezone.utc),
            },
        )
        .returning(CalibrationSummary)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_summary(session: AsyncSession) -> Optional[CalibrationSummary]:
    result = await session.execute(
        select(CalibrationSummary).where(CalibrationSummary.id == _SUMMARY_ROW_ID)
    )
    return result.scalar_one_or_none()
