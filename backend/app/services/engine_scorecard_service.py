"""
EngineScorecardService — Phase 5: Engine Scorecard.

Scores each engine layer on how effectively its output contributed to
positive trading outcomes.  All queries are read-only; no trades are modified.

Scoring model:
  signal_accuracy          — signals that had a matching executed OPEN_LONG decision
  opportunity_accuracy     — opportunities that scored >= 40 and led to OPEN_LONG
  strategy_execution_rate  — OPEN_LONG decisions that reached EXECUTED status
  execution_win_rate       — executed open positions that closed with pnl > 0
  risk_effectiveness       — BLOCKED decisions that, if executed, would have lost

Composite score: weighted average of the five engine scores.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.models.risk_event import RiskEvent
from app.models.signal import Signal
from app.models.trade_decision import TradeDecision

logger = get_logger(__name__)

_GRADE_THRESHOLDS = [("A", 80.0), ("B", 60.0), ("C", 40.0), ("D", 20.0), ("F", 0.0)]


def _grade(score: float) -> str:
    for letter, threshold in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100.0, 4)


class EngineScorecardService:
    """
    Computes the engine performance scorecard.

    Usage::

        svc = EngineScorecardService()
        scorecard = await svc.compute_scorecard(session)
    """

    async def compute_scorecard(self, session: AsyncSession) -> dict:
        """
        Run all scorecard queries and return a dict matching
        EngineScorecardResponse schema.
        """

        # ── 1. signal_accuracy ────────────────────────────────────────────────
        # Numerator: distinct condition_ids that appear in BOTH signals AND
        #            executed OPEN_LONG_* decisions (true intersection).
        # Denominator: total distinct condition_ids with at least one signal.
        total_signal_cids_res = await session.execute(
            select(func.count(func.distinct(Signal.condition_id)))
        )
        total_signal_cids: int = total_signal_cids_res.scalar_one() or 0

        # Subquery: condition_ids with at least one executed OPEN_LONG decision
        executed_cids_subq = (
            select(TradeDecision.condition_id)
            .where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "EXECUTED",
            )
            .distinct()
            .subquery()
        )

        # Intersection: signal condition_ids that also appear in the executed set
        signal_intersect_res = await session.execute(
            select(func.count(func.distinct(Signal.condition_id))).where(
                Signal.condition_id.in_(select(executed_cids_subq.c.condition_id))
            )
        )
        signal_accuracy_num: int = signal_intersect_res.scalar_one() or 0
        signal_score = _safe_pct(signal_accuracy_num, total_signal_cids)

        # ── 2. opportunity_accuracy ───────────────────────────────────────────
        # Numerator: distinct condition_ids with opp_score >= 40 that ALSO appear
        #            in executed OPEN_LONG decisions (true intersection).
        # Denominator: distinct condition_ids with opp_score >= 40.
        high_score_cids_res = await session.execute(
            select(func.count(func.distinct(Opportunity.condition_id))).where(
                Opportunity.opportunity_score >= 40.0
            )
        )
        high_score_opps: int = high_score_cids_res.scalar_one() or 0

        # Intersection: high-score opp condition_ids that were also executed
        opp_intersect_res = await session.execute(
            select(func.count(func.distinct(Opportunity.condition_id))).where(
                Opportunity.opportunity_score >= 40.0,
                Opportunity.condition_id.in_(select(executed_cids_subq.c.condition_id)),
            )
        )
        opp_accuracy_num: int = opp_intersect_res.scalar_one() or 0
        opp_score = _safe_pct(opp_accuracy_num, high_score_opps)

        # Total executed OPEN_LONG count (used for strategy_execution_rate)
        executed_open_all_res = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "EXECUTED",
            )
        )
        executed_open_all: int = executed_open_all_res.scalar_one() or 0

        # ── 3. strategy_execution_rate ────────────────────────────────────────
        # Numerator: OPEN_LONG decisions that reached EXECUTED status.
        # Denominator: all OPEN_LONG decisions (PENDING + RISK_APPROVED + BLOCKED + EXECUTED).
        total_open_res = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"])
            )
        )
        total_open: int = total_open_res.scalar_one() or 0

        strategy_exec_num = executed_open_all
        strategy_score = _safe_pct(strategy_exec_num, total_open)

        # ── 4. execution_win_rate ─────────────────────────────────────────────
        # Numerator: CLOSED positions with realized_pnl > 0.
        # Denominator: all CLOSED positions.
        total_closed_res = await session.execute(
            select(func.count(Position.id)).where(Position.status == "CLOSED")
        )
        total_closed: int = total_closed_res.scalar_one() or 0

        winning_closed_res = await session.execute(
            select(func.count(Position.id)).where(
                Position.status == "CLOSED",
                Position.realized_pnl > 0,
            )
        )
        winning_closed: int = winning_closed_res.scalar_one() or 0

        exec_win_score = _safe_pct(winning_closed, total_closed)

        # ── 5. risk_effectiveness ─────────────────────────────────────────────
        # BLOCKED decisions: we can't know how they would have performed.
        # Proxy: if > 0 BLOCKED exist and the overall win_rate < 50%, the risk
        # engine was protective.  Score as:
        #   blocked_count / (blocked_count + total_open) * 100
        # i.e. what fraction of potential open trades were filtered by risk.
        blocked_res = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.status == "BLOCKED"
            )
        )
        blocked_count: int = blocked_res.scalar_one() or 0

        risk_denom = blocked_count + total_open
        # Baseline: if risk blocked > 0 trades AND system win-rate < 50%, score it
        # higher (protective).  If win-rate >= 50%, blocking was neutral.
        if risk_denom > 0 and blocked_count > 0:
            base_risk = _safe_pct(blocked_count, risk_denom)
            # Bonus if overall win-rate was low (means risk filtering helped)
            overall_wr = _safe_pct(winning_closed, total_closed) if total_closed > 0 else 50.0
            bonus = max(0.0, (50.0 - overall_wr))  # 0 when wr>=50, up to 50 pts
            risk_score = min(100.0, base_risk + bonus * 0.5)
        else:
            # No blocked trades or no open trades: neutral 50 score (neither good nor bad)
            risk_score = 50.0

        risk_score = round(risk_score, 4)

        # ── Composite ─────────────────────────────────────────────────────────
        composite = round(
            0.20 * signal_score
            + 0.20 * opp_score
            + 0.20 * strategy_score
            + 0.25 * exec_win_score
            + 0.15 * risk_score,
            4,
        )

        logger.info(
            "Engine scorecard computed",
            signal_score=signal_score,
            opp_score=opp_score,
            strategy_score=strategy_score,
            exec_win_score=exec_win_score,
            risk_score=risk_score,
            composite=composite,
        )

        return {
            "signal_accuracy": {
                "score": signal_score,
                "label": "Signals that led to executed open positions",
                "numerator": signal_accuracy_num,
                "denominator": total_signal_cids,
            },
            "opportunity_accuracy": {
                "score": opp_score,
                "label": "High-score opportunities that converted to executed trades",
                "numerator": opp_accuracy_num,
                "denominator": high_score_opps,
            },
            "strategy_execution_rate": {
                "score": strategy_score,
                "label": "OPEN_LONG decisions that passed risk and were executed",
                "numerator": strategy_exec_num,
                "denominator": total_open,
            },
            "execution_win_rate": {
                "score": exec_win_score,
                "label": "Executed trades that closed profitably",
                "numerator": winning_closed,
                "denominator": total_closed,
            },
            "risk_effectiveness": {
                "score": risk_score,
                "label": "Risk engine protective filtering effectiveness",
                "numerator": blocked_count,
                "denominator": risk_denom,
            },
            "composite_score": composite,
            "composite_grade": _grade(composite),
        }
