"""
Performance Analytics Service — Layer 15.

Computes comprehensive trading performance metrics exclusively from CLOSED
positions.  No trading decisions are generated or modified here.

Metrics produced
----------------
total_trades       — count of CLOSED positions
winning_trades     — count where realized_pnl > 0
losing_trades      — count where realized_pnl < 0
win_rate           — winning_trades / total_trades * 100  (0–100 %)
gross_profit       — sum of positive realized_pnl values
gross_loss         — absolute sum of negative realized_pnl values
net_profit         — gross_profit - gross_loss
average_win        — mean of positive realized_pnl values
average_loss       — absolute mean of negative realized_pnl values
profit_factor      — gross_profit / gross_loss  (None when gross_loss == 0)
expectancy         — (win_rate/100 * avg_win) - (loss_rate/100 * avg_loss)
max_drawdown_usdc  — peak-to-trough equity drawdown from the closed_at curve
assets             — per-asset breakdown dict
timeframes         — per-timeframe breakdown dict
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.position import Position
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)


class PerformanceAnalyticsService:
    """
    Assembles performance analytics from CLOSED position data.

    All DB access is a single query via the position repository.
    All metric computation runs in Python — no N+1 queries.

    Usage::

        svc = PerformanceAnalyticsService()
        result = await svc.get_performance_analytics(session)
    """

    async def get_performance_analytics(self, session: AsyncSession) -> dict:
        """
        Generate a full performance analytics report.

        Returns
        -------
        dict  matching PerformanceAnalyticsResponse schema.
        """
        positions: list[Position] = await pos_repo.get_closed_positions(session)

        summary = self._compute_summary(positions)
        assets = self._compute_breakdown(positions, key="asset")
        timeframes = self._compute_breakdown(positions, key="timeframe")

        result = {
            **summary,
            "assets": assets,
            "timeframes": timeframes,
        }

        logger.info(
            "Performance analytics generated",
            total_trades=summary["total_trades"],
            net_profit=summary["net_profit"],
            win_rate=summary["win_rate"],
        )

        return result

    # ── Internal computation ──────────────────────────────────────────────────

    @staticmethod
    def _compute_summary(positions: list[Position]) -> dict:
        """Compute aggregate metrics across all closed positions."""
        pnls = [float(p.realized_pnl or 0.0) for p in positions]

        total_trades = len(pnls)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_profit": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "profit_factor": None,
                "expectancy": 0.0,
                "max_drawdown_usdc": 0.0,
            }

        wins = [v for v in pnls if v > 0]
        losses = [v for v in pnls if v < 0]

        winning_trades = len(wins)
        losing_trades = len(losses)

        gross_profit = round(sum(wins), 6)
        gross_loss = round(abs(sum(losses)), 6)
        net_profit = round(gross_profit - gross_loss, 6)

        win_rate = round((winning_trades / total_trades) * 100, 4)
        loss_rate = round(100.0 - win_rate, 4)

        average_win = round(sum(wins) / winning_trades, 6) if wins else 0.0
        average_loss = round(abs(sum(losses) / losing_trades), 6) if losses else 0.0

        profit_factor: Optional[float] = (
            round(gross_profit / gross_loss, 6) if gross_loss > 0 else None
        )

        expectancy = round(
            (win_rate / 100.0 * average_win) - (loss_rate / 100.0 * average_loss), 6
        )

        max_drawdown_usdc = round(
            PerformanceAnalyticsService._compute_max_drawdown(pnls), 6
        )

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_profit": net_profit,
            "average_win": average_win,
            "average_loss": average_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_drawdown_usdc": max_drawdown_usdc,
        }

    @staticmethod
    def _compute_max_drawdown(pnls: list[float]) -> float:
        """
        Build an equity curve (cumulative sum of realized PnL in closed_at order)
        and return the maximum peak-to-trough drawdown in USDC.

        The positions list is already ordered by closed_at ascending from the
        repository query, so pnls is already in chronological order.
        """
        if not pnls:
            return 0.0

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0

        for pnl in pnls:
            equity += pnl
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    @staticmethod
    def _compute_breakdown(
        positions: list[Position],
        key: str,
    ) -> dict[str, dict]:
        """
        Group closed positions by `key` (e.g. "asset" or "timeframe") and
        compute per-group trade statistics.
        """
        groups: dict[str, list[float]] = {}
        for p in positions:
            group_val = getattr(p, key, "unknown") or "unknown"
            pnl = float(p.realized_pnl or 0.0)
            groups.setdefault(group_val, []).append(pnl)

        result = {}
        for group_val, pnls in sorted(groups.items()):
            wins = [v for v in pnls if v > 0]
            losses = [v for v in pnls if v < 0]
            total = len(pnls)
            winning = len(wins)
            losing = len(losses)
            result[group_val] = {
                "trades": total,
                "wins": winning,
                "losses": losing,
                "win_rate": round((winning / total) * 100, 4) if total else 0.0,
                "net_profit": round(sum(pnls), 6),
            }

        return result
