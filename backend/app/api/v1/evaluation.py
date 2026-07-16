"""
Evaluation router — Phase 5: Trade Evaluation & Engine Scorecard.

GET /evaluation/summary    — aggregate quality stats across all evaluated trades
GET /evaluation/scorecard  — engine performance scorecard
GET /evaluation/grades     — grade distribution only
GET /evaluation/{position_id} — evaluation for a specific position
POST /evaluation/run       — trigger evaluation of all un-evaluated closed trades
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.evaluation import (
    EngineScorecardResponse,
    EvaluationSummaryResponse,
    GradeDistribution,
    TradeEvaluationSchema,
)
from app.services.engine_scorecard_service import EngineScorecardService
from app.services.trade_evaluation_service import TradeEvaluationService

logger = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])

_eval_service = TradeEvaluationService()
_scorecard_service = EngineScorecardService()


@router.get("/summary", response_model=EvaluationSummaryResponse)
async def get_evaluation_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Aggregate quality statistics across all persisted trade evaluations.

    Returns counts, average component scores, grade distribution, and the
    best/worst-performing assets by average quality score.
    All values are zero / null when no evaluations exist yet.
    """
    data = await _eval_service.get_evaluation_summary(session)
    return EvaluationSummaryResponse(**data)


@router.get("/scorecard", response_model=EngineScorecardResponse)
async def get_engine_scorecard(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Engine performance scorecard.

    Scores each pipeline layer (Signal → Opportunity → Strategy → Execution → Risk)
    on how effectively its output led to positive trading outcomes.
    Includes a weighted composite score and letter grade.
    """
    data = await _scorecard_service.compute_scorecard(session)
    return EngineScorecardResponse(**data)


@router.get("/grades", response_model=GradeDistribution)
async def get_grade_distribution(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Grade distribution across all evaluated trades.

    A convenience endpoint returning only the A/B/C/D/F counts.
    """
    data = await _eval_service.get_evaluation_summary(session)
    return GradeDistribution(**data["grade_distribution"])


@router.get("/{position_id}", response_model=TradeEvaluationSchema)
async def get_position_evaluation(
    position_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trade evaluation for a specific closed position.

    Returns 404 if no evaluation record exists for this position.
    Run POST /evaluation/run first to populate evaluations.
    """
    ev = await _eval_service.get_evaluation_for_position(position_id, session)
    if ev is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation found for position {position_id}. "
                   "Run POST /evaluation/run to generate evaluations.",
        )
    return TradeEvaluationSchema.model_validate(ev)


@router.post("/run", response_model=dict)
async def run_evaluations(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trigger evaluation of all closed positions that have not yet been evaluated.

    Idempotent — already-evaluated positions are skipped.
    Returns counts of newly evaluated and total positions processed.
    """
    new_evals = await _eval_service.evaluate_all(session)
    logger.info("Evaluation run completed", new_evaluations=len(new_evals))
    return {
        "status": "ok",
        "new_evaluations": len(new_evals),
        "message": (
            f"Evaluated {len(new_evals)} new trade(s). "
            "Use GET /evaluation/summary for aggregate stats."
        ),
    }
