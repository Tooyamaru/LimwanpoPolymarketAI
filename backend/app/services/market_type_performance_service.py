"""
MarketTypePerformanceService — Priority 5: Market Type Performance.

Recomputes accuracy, win rate, average pnl, max drawdown, and average
confidence for every (asset, timeframe, market_type) combination seen in
outcome_learnings.  Runs after every OutcomeLearningService batch.

Max drawdown is computed from the cumulative realized_pnl sequence of that
segment's trades, ordered by evaluated_at (largest peak-to-trough decline).

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.outcome_learning import OutcomeLearning
from app.repositories import market_type_performance_repository as mtp_repo
from app.repositories import outcome_learning_repository as ol_repo

logger = get_logger(__name__)


def _max_drawdown(pnl_sequence: list[float]) -> Optional[float]:
    """Largest peak-to-trough decline in the cumulative pnl curve."""
    if not pnl_sequence:
        return None
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnl_sequence:
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        max_dd = max(max_dd, drawdown)
    return round(max_dd, 6)


class MarketTypePerformanceService:
    """
    Priority 5 — Market Type Performance.

    Usage::

        svc = MarketTypePerformanceService()
        result = await svc.recompute(session)
    """

    async def recompute(self, session: AsyncSession) -> dict:
        outcomes = await ol_repo.get_all_outcomes(session)

        groups: dict[tuple[str, str, str], list[OutcomeLearning]] = defaultdict(list)
        for o in outcomes:
            market_type = o.market_type or "UNKNOWN"
            groups[(o.asset, o.timeframe, market_type)].append(o)

        if not groups:
            logger.debug("Market type performance: no outcomes yet")
            return {}

        segments_written = 0
        for (asset, timeframe, market_type), rows in groups.items():
            decided = [r for r in rows if r.correct is not None]
            wins = sum(1 for r in decided if r.correct is True)
            losses = sum(1 for r in decided if r.correct is False)
            total_trades = sum(1 for r in rows if r.outcome_type == "POSITION")

            accuracy = (
                round(wins / (wins + losses) * 100.0, 2)
                if (wins + losses) > 0 else None
            )

            pnl_rows = sorted(
                (r for r in rows if r.actual_pnl is not None),
                key=lambda r: r.evaluated_at,
            )
            pnl_vals = [r.actual_pnl for r in pnl_rows]
            avg_pnl = round(sum(pnl_vals) / len(pnl_vals), 6) if pnl_vals else None
            win_rate = (
                round(sum(1 for p in pnl_vals if p > 0) / len(pnl_vals) * 100.0, 2)
                if pnl_vals else None
            )
            max_drawdown = _max_drawdown(pnl_vals)

            conf_vals = [r.confidence for r in rows if r.confidence is not None]
            avg_confidence = round(sum(conf_vals) / len(conf_vals), 2) if conf_vals else None

            await mtp_repo.upsert_market_type_performance(
                session,
                asset=asset,
                timeframe=timeframe,
                market_type=market_type,
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                accuracy=accuracy,
                avg_pnl=avg_pnl,
                max_drawdown=max_drawdown,
                avg_confidence=avg_confidence,
            )
            segments_written += 1

        logger.info("Market type performance recomputed", segments=segments_written)
        return {"segments": segments_written}
