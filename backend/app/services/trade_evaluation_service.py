"""
TradeEvaluationService — Phase 5: Trade Evaluation.

Computes a per-trade quality score for every CLOSED position.

Scoring model (four components, each 0–100):
  entry_quality   (25%) — how efficient was the entry price vs mid at open
  exit_quality    (25%) — how efficient was the exit vs peak PnL opportunity
  timing_score    (25%) — hold duration relative to the asset's typical window
  pnl_efficiency  (25%) — realized PnL as % of theoretical max (peak_pnl_usdc)

Grade thresholds:
  A ≥ 80  |  B ≥ 60  |  C ≥ 40  |  D ≥ 20  |  F < 20
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.models.trade_evaluation import TradeEvaluation
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)

# Typical hold windows per timeframe (minutes) — used for timing score
_TYPICAL_HOLD: dict[str, float] = {
    "5m": 15.0,
    "15m": 45.0,
    "1H": 180.0,
}
_DEFAULT_HOLD = 60.0  # fallback for unknown timeframes

# Grade boundaries
_GRADES = [("A", 80.0), ("B", 60.0), ("C", 40.0), ("D", 20.0), ("F", 0.0)]


def _grade(score: float) -> str:
    for letter, threshold in _GRADES:
        if score >= threshold:
            return letter
    return "F"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


class TradeEvaluationService:
    """
    Evaluates individual closed trades and persists results to trade_evaluations.

    Usage::

        svc = TradeEvaluationService()
        evaluation = await svc.evaluate_position(position, session)
        summary    = await svc.get_evaluation_summary(session)
        evals      = await svc.get_all_evaluations(session)
    """

    # ── Public API ────────────────────────────────────────────────────────────

    async def evaluate_all(self, session: AsyncSession) -> list[TradeEvaluation]:
        """
        Evaluate every CLOSED position that does not yet have an evaluation,
        persist results, and return all persisted evaluations.
        """
        positions = await pos_repo.get_closed_positions(session)

        # Fetch existing evaluations to skip already-evaluated positions
        existing_res = await session.execute(select(TradeEvaluation.position_id))
        already_done: set[int] = {row[0] for row in existing_res.fetchall()}

        new_evals: list[TradeEvaluation] = []
        for pos in positions:
            if pos.id in already_done:
                continue
            entry_metrics = await self._compute_entry_quality_metrics(pos, session)
            ev = self._compute_evaluation(pos, entry_metrics)
            session.add(ev)
            new_evals.append(ev)

        if new_evals:
            await session.flush()

        logger.info(
            "Trade evaluations completed",
            new_evaluations=len(new_evals),
            total_positions=len(positions),
        )
        return new_evals

    async def evaluate_position(
        self, position: Position, session: AsyncSession
    ) -> TradeEvaluation:
        """
        Evaluate a single closed position.  Upserts by deleting any existing
        evaluation for that position_id before inserting the new one.
        """
        existing = await session.execute(
            select(TradeEvaluation).where(
                TradeEvaluation.position_id == position.id
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.flush()

        entry_metrics = await self._compute_entry_quality_metrics(position, session)
        ev = self._compute_evaluation(position, entry_metrics)
        session.add(ev)
        await session.flush()
        return ev

    async def get_all_evaluations(
        self, session: AsyncSession, limit: int = 500, offset: int = 0
    ) -> list[TradeEvaluation]:
        """Return all persisted evaluations ordered by evaluated_at DESC."""
        res = await session.execute(
            select(TradeEvaluation)
            .order_by(TradeEvaluation.evaluated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(res.scalars().all())

    async def get_evaluation_for_position(
        self, position_id: int, session: AsyncSession
    ) -> Optional[TradeEvaluation]:
        res = await session.execute(
            select(TradeEvaluation).where(TradeEvaluation.position_id == position_id)
        )
        return res.scalar_one_or_none()

    async def get_evaluation_summary(self, session: AsyncSession) -> dict:
        """
        Aggregate statistics across all persisted evaluations using SQL aggregates.
        Returns a dict matching EvaluationSummaryResponse schema.
        """
        from sqlalchemy import case

        # Single aggregation query for scalar metrics
        agg_res = await session.execute(
            select(
                func.count(TradeEvaluation.id).label("total"),
                func.avg(TradeEvaluation.quality_score).label("avg_quality"),
                func.avg(TradeEvaluation.entry_quality).label("avg_entry"),
                func.avg(TradeEvaluation.exit_quality).label("avg_exit"),
                func.avg(TradeEvaluation.timing_score).label("avg_timing"),
                func.avg(TradeEvaluation.pnl_efficiency).label("avg_pnl"),
            )
        )
        agg = agg_res.one()

        if not agg.total:
            return {
                "total_evaluated": 0,
                "avg_quality_score": 0.0,
                "avg_entry_quality": 0.0,
                "avg_exit_quality": 0.0,
                "avg_timing_score": 0.0,
                "avg_pnl_efficiency": 0.0,
                "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                "best_grade_asset": None,
                "worst_grade_asset": None,
            }

        # Grade distribution via SQL GROUP BY
        grade_res = await session.execute(
            select(
                TradeEvaluation.grade,
                func.count(TradeEvaluation.id).label("cnt"),
            ).group_by(TradeEvaluation.grade)
        )
        grades: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for row in grade_res.all():
            grades[row.grade] = row.cnt

        # Per-asset avg via SQL GROUP BY — for best/worst asset only
        asset_res = await session.execute(
            select(
                TradeEvaluation.asset,
                func.avg(TradeEvaluation.quality_score).label("avg_q"),
            ).group_by(TradeEvaluation.asset)
        )
        asset_rows = asset_res.all()
        best_asset = max(asset_rows, key=lambda r: r.avg_q).asset if asset_rows else None
        worst_asset = min(asset_rows, key=lambda r: r.avg_q).asset if asset_rows else None

        return {
            "total_evaluated": agg.total,
            "avg_quality_score": round(float(agg.avg_quality or 0.0), 4),
            "avg_entry_quality": round(float(agg.avg_entry or 0.0), 4),
            "avg_exit_quality": round(float(agg.avg_exit or 0.0), 4),
            "avg_timing_score": round(float(agg.avg_timing or 0.0), 4),
            "avg_pnl_efficiency": round(float(agg.avg_pnl or 0.0), 4),
            "grade_distribution": grades,
            "best_grade_asset": best_asset,
            "worst_grade_asset": worst_asset,
        }

    # ── Internal computation ──────────────────────────────────────────────────

    async def _compute_entry_quality_metrics(
        self, pos: Position, session: AsyncSession
    ) -> dict:
        """
        Priority 4 — Entry Quality Validation.

        Looks at every MarketPriceSnapshot captured for this market between
        entry (opened_at) and exit (closed_at) and compares the entry fill
        price against the range of prices actually available while the
        position was open, to see how efficient the entry was.

        Returns a dict with best_price_after_entry, worst_price_after_entry,
        avg_price_after_entry, entry_efficiency (0-100), entry_timing_label.
        """
        empty = {
            "best_price_after_entry": None,
            "worst_price_after_entry": None,
            "avg_price_after_entry": None,
            "entry_efficiency": None,
            "entry_timing_label": "UNKNOWN",
        }
        if pos.opened_at is None:
            return empty

        opened = pos.opened_at
        closed = pos.closed_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        if closed is not None and closed.tzinfo is None:
            closed = closed.replace(tzinfo=timezone.utc)

        query = select(MarketPriceSnapshot).where(
            MarketPriceSnapshot.condition_id == pos.condition_id,
            MarketPriceSnapshot.captured_at >= opened,
        )
        if closed is not None:
            query = query.where(MarketPriceSnapshot.captured_at <= closed)

        result = await session.execute(query)
        snapshots = list(result.scalars().all())

        prices: list[float] = []
        for snap in snapshots:
            if pos.side == "LONG_YES":
                price = snap.yes_mid
            else:
                price = snap.no_mid if snap.no_mid is not None else (
                    1.0 - snap.yes_mid if snap.yes_mid is not None else None
                )
            if price is not None:
                prices.append(price)

        if not prices:
            return empty

        best_price = min(prices)   # cheapest available entry (best for a buyer)
        worst_price = max(prices)  # most expensive available entry (worst for a buyer)
        avg_price = round(sum(prices) / len(prices), 6)
        entry_price = float(pos.entry_price)

        if worst_price == best_price:
            entry_efficiency = 50.0
        else:
            entry_efficiency = _clamp(
                (worst_price - entry_price) / (worst_price - best_price) * 100.0
            )

        if entry_price <= best_price + 0.01:
            timing_label = "OPTIMAL"
        elif entry_efficiency >= 60.0:
            timing_label = "EARLY"
        elif entry_efficiency >= 30.0:
            timing_label = "LATE"
        else:
            timing_label = "POOR"

        return {
            "best_price_after_entry": round(best_price, 6),
            "worst_price_after_entry": round(worst_price, 6),
            "avg_price_after_entry": avg_price,
            "entry_efficiency": round(entry_efficiency, 4),
            "entry_timing_label": timing_label,
        }

    def _compute_evaluation(
        self, pos: Position, entry_metrics: Optional[dict] = None
    ) -> TradeEvaluation:
        """Core scoring logic for a single closed position."""
        realized = float(pos.realized_pnl or 0.0)
        peak = float(pos.peak_pnl_usdc or 0.0)

        # ── entry_quality ─────────────────────────────────────────────────────
        # Proxy: we don't have order book history, so we grade by whether the
        # fill happened at a tight spread. entry_price vs a neutral 0.50 mid:
        # closer to 0.50 = better for either side (lower risk, tighter market).
        # Score 100 if entry_price is within 0.01 of 0.50, grades down linearly.
        entry_price = float(pos.entry_price or 0.50)
        entry_deviation = abs(entry_price - 0.50)
        # At 0.50 → 100, at 0.40/0.60 → 0
        entry_quality = _clamp((1.0 - entry_deviation / 0.10) * 100.0)

        # ── exit_quality ──────────────────────────────────────────────────────
        # How well did we capture the available profit?
        # If peak > 0 and realized < peak → we left money on the table.
        # If realized >= peak (including winning profitable trades) → 100.
        if peak > 0 and realized < peak:
            exit_quality = _clamp((realized / peak) * 100.0)
        elif realized <= 0 and peak <= 0:
            # All-loss trade: no peak; full exit score since there was nothing to capture
            exit_quality = 50.0
        else:
            exit_quality = 100.0

        # ── timing_score ──────────────────────────────────────────────────────
        # Compare actual hold_minutes vs typical window for this timeframe.
        # Perfect score when hold == typical; penalise both too short and too long.
        hold_min: Optional[float] = None
        if pos.opened_at is not None and pos.closed_at is not None:
            opened = pos.opened_at
            closed = pos.closed_at
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            if closed.tzinfo is None:
                closed = closed.replace(tzinfo=timezone.utc)
            hold_min = (closed - opened).total_seconds() / 60.0

        typical = _TYPICAL_HOLD.get(pos.timeframe or "", _DEFAULT_HOLD)
        if hold_min is not None and typical > 0:
            ratio = hold_min / typical
            # Score peaks at ratio=1.0, falls off symmetrically
            timing_score = _clamp(100.0 - abs(ratio - 1.0) * 80.0)
        else:
            timing_score = 50.0  # unknown — neutral

        # ── pnl_efficiency ────────────────────────────────────────────────────
        # Realized PnL as % of theoretical max (peak_pnl_usdc).
        # 100 = we captured everything available; 0 = all-loss or no peak.
        if peak > 0 and realized > 0:
            pnl_efficiency = _clamp((realized / peak) * 100.0)
        elif peak > 0 and realized <= 0:
            # Peak was positive but we still lost — worst efficiency
            pnl_efficiency = 0.0
        elif peak <= 0 and realized > 0:
            # No peak recorded but trade was profitable — treat as moderate
            pnl_efficiency = 50.0
        else:
            # Both non-positive: all-loss trade
            pnl_efficiency = 0.0

        # ── composite ─────────────────────────────────────────────────────────
        quality_score = round(
            0.25 * entry_quality
            + 0.25 * exit_quality
            + 0.25 * timing_score
            + 0.25 * pnl_efficiency,
            4,
        )

        # ── theoretical max ───────────────────────────────────────────────────
        theoretical_max = peak if peak > 0 else None

        metrics = entry_metrics or {}

        return TradeEvaluation(
            position_id=pos.id,
            asset=pos.asset or "UNKNOWN",
            timeframe=pos.timeframe or "UNKNOWN",
            close_reason=getattr(pos, "close_reason", None),
            hold_minutes=round(hold_min, 4) if hold_min is not None else None,
            entry_quality=round(entry_quality, 4),
            exit_quality=round(exit_quality, 4),
            timing_score=round(timing_score, 4),
            pnl_efficiency=round(pnl_efficiency, 4),
            quality_score=quality_score,
            grade=_grade(quality_score),
            opportunity_score_at_entry=None,  # populated by evaluate_with_context
            signal_confidence_at_entry=None,
            realized_pnl=realized,
            theoretical_max_pnl=theoretical_max,
            best_price_after_entry=metrics.get("best_price_after_entry"),
            worst_price_after_entry=metrics.get("worst_price_after_entry"),
            avg_price_after_entry=metrics.get("avg_price_after_entry"),
            entry_efficiency=metrics.get("entry_efficiency"),
            entry_timing_label=metrics.get("entry_timing_label", "UNKNOWN"),
        )
