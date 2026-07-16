"""
EnginePerformanceService — Priority 2: Engine Performance Tracking.

Computes per-engine accuracy, wins, losses, contribution scores from all
outcome_learnings rows.  Runs after every OutcomeLearningService batch.

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.outcome_learning import OutcomeLearning
from app.repositories import engine_performance_repository as ep_repo

logger = get_logger(__name__)

# Engine names → how to read their direction from OutcomeLearning
# Maps engine_name → (direction_field, bullish_values, bearish_values)
ENGINE_DIRECTION_MAP: dict[str, tuple[str, set[str], set[str]]] = {
    "opportunity": ("opportunity_direction", {"BUY_YES"}, {"BUY_NO"}),
    "orderbook":   ("orderbook_direction",   {"BULLISH"}, {"BEARISH"}),
    "momentum":    ("momentum_direction",    {"BULLISH"}, {"BEARISH"}),
    "trend":       ("trend_direction",       {"UP"},      {"DOWN"}),
    "funding":     ("funding_direction",     {"BULLISH"}, {"BEARISH"}),
}


def _engine_was_correct(
    engine_name: str,
    outcome_row: OutcomeLearning,
) -> Optional[bool]:
    """
    Determine if a specific engine's direction prediction was correct.

    Returns True (correct), False (wrong), or None (no data / neutral).
    """
    mapping = ENGINE_DIRECTION_MAP.get(engine_name)
    if mapping is None:
        return None

    field_name, bullish_vals, bearish_vals = mapping
    direction: Optional[str] = getattr(outcome_row, field_name, None)
    prediction = outcome_row.prediction   # BUY_YES | BUY_NO | WAIT
    correct    = outcome_row.correct      # True | False | None

    if direction is None or correct is None:
        return None

    # Determine engine's implied stance
    if direction in bullish_vals:
        engine_says_yes = True
    elif direction in bearish_vals:
        engine_says_yes = False
    else:
        return None  # NEUTRAL / no signal

    # Determine what "correct" means directionally
    if prediction == "BUY_YES":
        ai_went_yes = True
    elif prediction == "BUY_NO":
        ai_went_yes = False
    else:
        return None  # AI said WAIT — can't attribute to a specific direction

    # Engine is "correct" if it pointed the same way as the winning side
    # (i.e. the AI's prediction was correct and engine agreed, OR
    #  the AI was wrong and engine disagreed)
    engine_agreed_with_ai = (engine_says_yes == ai_went_yes)
    if correct:
        return engine_agreed_with_ai    # AI was right, engine agreed → engine correct
    else:
        return not engine_agreed_with_ai  # AI was wrong, engine disagreed → engine was right


class EnginePerformanceService:
    """
    Computes and persists per-engine performance stats from outcome_learnings.

    Usage::

        svc = EnginePerformanceService()
        await svc.recompute_from_all_outcomes(session)
    """

    async def recompute_from_all_outcomes(self, session: AsyncSession) -> dict:
        """
        Full recompute: read all outcome_learnings, tally per-engine wins/losses.
        This is O(N × engines) but N is small (markets evaluated, not trades).
        """
        result = await session.execute(select(OutcomeLearning))
        outcomes = list(result.scalars().all())

        if not outcomes:
            logger.debug("Engine performance: no outcomes yet")
            return {}

        total_outcomes_with_result = sum(1 for o in outcomes if o.correct is not None)

        # First pass: compute per-engine contribution_score so contribution_pct
        # (Priority 2) can be derived as each engine's share of the total.
        raw_scores: dict[str, Optional[float]] = {}
        for engine_name in ENGINE_DIRECTION_MAP:
            wins = losses = 0
            for outcome in outcomes:
                engine_correct = _engine_was_correct(engine_name, outcome)
                if engine_correct is True:
                    wins += 1
                elif engine_correct is False:
                    losses += 1
            total_evaluated = wins + losses
            accuracy = (wins / total_evaluated * 100.0) if total_evaluated > 0 else None
            participation_rate = (
                total_evaluated / total_outcomes_with_result
                if total_outcomes_with_result > 0 else 0.0
            )
            raw_scores[engine_name] = (
                (accuracy / 100.0) * participation_rate * 100.0
                if accuracy is not None else None
            )

        total_contribution = sum(v for v in raw_scores.values() if v is not None)

        summaries: dict[str, dict] = {}
        for engine_name in ENGINE_DIRECTION_MAP:
            wins        = 0
            losses      = 0
            abstentions = 0
            conf_correct: list[float] = []
            conf_wrong:   list[float] = []

            for outcome in outcomes:
                engine_correct = _engine_was_correct(engine_name, outcome)

                if engine_correct is None:
                    abstentions += 1
                elif engine_correct:
                    wins += 1
                    if outcome.confidence:
                        conf_correct.append(outcome.confidence)
                else:
                    losses += 1
                    if outcome.confidence:
                        conf_wrong.append(outcome.confidence)

            total_evaluated = wins + losses
            accuracy = (
                round(wins / total_evaluated * 100.0, 2)
                if total_evaluated > 0 else None
            )

            # Contribution score: accuracy × participation_rate
            participation_rate = (
                total_evaluated / total_outcomes_with_result
                if total_outcomes_with_result > 0 else 0.0
            )
            contribution_score = (
                round((accuracy / 100.0) * participation_rate * 100.0, 2)
                if accuracy is not None else None
            )

            avg_conf_correct = (
                round(sum(conf_correct) / len(conf_correct), 2)
                if conf_correct else None
            )
            avg_conf_wrong = (
                round(sum(conf_wrong) / len(conf_wrong), 2)
                if conf_wrong else None
            )

            # Priority 2: contribution_pct — this engine's share of total
            # contribution_score across all engines (helped_correct/wrong/
            # neutral are exposed via wins/losses/abstentions in the schema).
            contribution_pct = (
                round(contribution_score / total_contribution * 100.0, 2)
                if contribution_score is not None and total_contribution > 0
                else None
            )

            await ep_repo.upsert_engine_performance(
                session,
                engine_name=engine_name,
                wins=wins,
                losses=losses,
                abstentions=abstentions,
                total_evaluated=total_evaluated,
                accuracy=accuracy,
                avg_confidence_when_correct=avg_conf_correct,
                avg_confidence_when_wrong=avg_conf_wrong,
                contribution_score=contribution_score,
                contribution_pct=contribution_pct,
            )

            summaries[engine_name] = {
                "wins": wins,
                "losses": losses,
                "abstentions": abstentions,
                "accuracy": accuracy,
            }

        logger.info(
            "Engine performance stats recomputed",
            engines=len(summaries),
            outcomes_used=len(outcomes),
        )
        return summaries
