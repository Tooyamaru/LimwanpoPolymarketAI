"""
Performance Analytics Service — Layer 15.

Computes comprehensive trading performance metrics exclusively from CLOSED
positions.  No trading decisions are generated or modified here.

Core metrics
------------
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

Phase 4 (Part C) additions
---------------------------
signal_precision           — % of closed trades that were profitable (same as
                             win_rate in this system; every trade is signal-triggered)
avg_winner_duration_minutes — avg hold time for winning positions
avg_loser_duration_minutes  — avg hold time for losing positions
avg_fee_usdc                — avg total fee per closed trade (entry + exit)
avg_slippage_usdc           — always 0.0 in paper mode (no slippage simulated)
avg_time_to_stop_minutes    — avg hold time for STOP_LOSS exits
avg_time_to_profit_minutes  — avg hold time for PROFIT_TARGET exits
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.position import Position
from app.models.trade_decision import TradeDecision
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)


class PerformanceAnalyticsService:
    """
    Assembles performance analytics from CLOSED position data.

    All DB access is a minimal set of queries via the position repository.
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

        # ── Opportunity conversion rate ────────────────────────────────────────
        total_res = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"])
            )
        )
        executed_res = await session.execute(
            select(func.count(TradeDecision.id)).where(
                TradeDecision.decision.in_(["OPEN_LONG_YES", "OPEN_LONG_NO"]),
                TradeDecision.status == "EXECUTED",
            )
        )
        total_open_decisions: int = total_res.scalar_one() or 0
        executed_open_decisions: int = executed_res.scalar_one() or 0
        opportunity_conversion_rate = (
            round(executed_open_decisions / total_open_decisions * 100.0, 4)
            if total_open_decisions > 0 else 0.0
        )

        summary = self._compute_summary(positions)
        assets = self._compute_breakdown(positions, key="asset")
        timeframes = self._compute_breakdown(positions, key="timeframe")

        result = {
            **summary,
            "assets": assets,
            "timeframes": timeframes,
            "opportunity_conversion_rate": opportunity_conversion_rate,
        }

        logger.info(
            "Performance analytics generated",
            total_trades=summary["total_trades"],
            net_profit=summary["net_profit"],
            win_rate=summary["win_rate"],
            opportunity_conversion_rate=opportunity_conversion_rate,
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
                "avg_hold_time_minutes": 0.0,
                "longest_hold_time_minutes": 0.0,
                "shortest_hold_time_minutes": 0.0,
                "mae_usdc": 0.0,
                "mfe_usdc": 0.0,
                # Phase 4 Part C
                "signal_precision": 0.0,
                "avg_winner_duration_minutes": 0.0,
                "avg_loser_duration_minutes": 0.0,
                "avg_fee_usdc": 0.0,
                "avg_slippage_usdc": 0.0,
                "avg_time_to_stop_minutes": 0.0,
                "avg_time_to_profit_minutes": 0.0,
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

        # ── Holding times ────────────────────────────────────────────────────
        hold_times: list[float] = []
        for p in positions:
            if p.opened_at is not None and p.closed_at is not None:
                opened = p.opened_at
                closed = p.closed_at
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                if closed.tzinfo is None:
                    closed = closed.replace(tzinfo=timezone.utc)
                hold_times.append((closed - opened).total_seconds() / 60.0)

        avg_hold_time = round(sum(hold_times) / len(hold_times), 4) if hold_times else 0.0
        longest_hold = round(max(hold_times), 4) if hold_times else 0.0
        shortest_hold = round(min(hold_times), 4) if hold_times else 0.0

        # ── MAE / MFE (realized proxies) ─────────────────────────────────────
        mae_usdc = round(min(pnls), 6)
        mfe_usdc = round(max(pnls), 6)

        # ── Phase 4 Part C: extended metrics ─────────────────────────────────

        # signal_precision: in this system every trade is signal-triggered,
        # so precision == win_rate (% of signals that led to a profitable close).
        signal_precision = win_rate

        # Avg hold time split by trade outcome
        winner_times: list[float] = []
        loser_times: list[float] = []
        stop_times: list[float] = []
        profit_times: list[float] = []
        fees: list[float] = []

        for p in positions:
            pnl = float(p.realized_pnl or 0.0)
            hold_min: Optional[float] = None

            if p.opened_at is not None and p.closed_at is not None:
                opened = p.opened_at
                closed = p.closed_at
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                if closed.tzinfo is None:
                    closed = closed.replace(tzinfo=timezone.utc)
                hold_min = (closed - opened).total_seconds() / 60.0

            if hold_min is not None:
                if pnl > 0:
                    winner_times.append(hold_min)
                elif pnl < 0:
                    loser_times.append(hold_min)

                close_reason = getattr(p, "close_reason", None)
                if close_reason == "STOP_LOSS":
                    stop_times.append(hold_min)
                elif close_reason == "PROFIT_TARGET":
                    profit_times.append(hold_min)

            # Fees (Phase 4 Part D): total_fee_usdc stored on position
            fee = float(getattr(p, "total_fee_usdc", None) or 0.0)
            fees.append(fee)

        avg_winner_duration = (
            round(sum(winner_times) / len(winner_times), 4) if winner_times else 0.0
        )
        avg_loser_duration = (
            round(sum(loser_times) / len(loser_times), 4) if loser_times else 0.0
        )
        avg_fee = round(sum(fees) / len(fees), 6) if fees else 0.0
        avg_time_to_stop = (
            round(sum(stop_times) / len(stop_times), 4) if stop_times else 0.0
        )
        avg_time_to_profit = (
            round(sum(profit_times) / len(profit_times), 4) if profit_times else 0.0
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
            "avg_hold_time_minutes": avg_hold_time,
            "longest_hold_time_minutes": longest_hold,
            "shortest_hold_time_minutes": shortest_hold,
            "mae_usdc": mae_usdc,
            "mfe_usdc": mfe_usdc,
            # Phase 4 Part C
            "signal_precision": signal_precision,
            "avg_winner_duration_minutes": avg_winner_duration,
            "avg_loser_duration_minutes": avg_loser_duration,
            "avg_fee_usdc": avg_fee,
            "avg_slippage_usdc": 0.0,  # paper mode: always zero
            "avg_time_to_stop_minutes": avg_time_to_stop,
            "avg_time_to_profit_minutes": avg_time_to_profit,
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
