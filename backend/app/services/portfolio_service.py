"""
Portfolio Service — Layer 10: Portfolio Reporting.

Assembles portfolio-level summaries from cross-layer data.
Read-only: delegates all DB reads to portfolio_repository.

Does NOT generate trades, modify positions, or interact with
Layers 1–9 pipelines.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import portfolio_repository as repo

logger = get_logger(__name__)


class PortfolioService:
    """
    Aggregates portfolio metrics for reporting endpoints.

    Usage::

        svc = PortfolioService()
        summary = await svc.get_portfolio_summary(session)
    """

    async def get_portfolio_summary(self, session: AsyncSession) -> dict:
        """
        High-level portfolio snapshot combining positions, orders,
        and trade decision counts.

        Returns
        -------
        dict matching PortfolioSummaryResponse schema.
        """
        data = await repo.get_portfolio_summary(session)
        logger.debug("Portfolio summary assembled", **data)
        return data

    async def get_position_summary(self, session: AsyncSession) -> dict:
        """
        Position breakdown by status, asset, and side.

        Returns
        -------
        dict matching PositionSummaryResponse schema.
        """
        data = await repo.get_position_summary(session)
        logger.debug(
            "Position summary assembled",
            total=data["total_positions"],
            open=data["open_positions"],
        )
        return data

    async def get_order_summary(self, session: AsyncSession) -> dict:
        """
        Order breakdown by status, asset, and side.

        Returns
        -------
        dict matching OrderSummaryResponse schema.
        """
        data = await repo.get_order_summary(session)
        logger.debug(
            "Order summary assembled",
            total=data["total_orders"],
            filled=data["filled_orders"],
        )
        return data

    async def get_risk_summary(self, session: AsyncSession) -> dict:
        """
        Risk check statistics: allowed/blocked counts and block reasons.

        Returns
        -------
        dict matching RiskSummaryResponse schema.
        """
        data = await repo.get_risk_summary(session)
        logger.debug(
            "Risk summary assembled",
            total_checked=data["total_checked"],
            block_rate_pct=data["block_rate_pct"],
        )
        return data

    async def get_accounting_summary(self, session: AsyncSession) -> dict:
        """
        Global accounting snapshot — source of truth for dashboard financial widgets.

        Returns
        -------
        dict matching AccountingResponse schema (spec §9).
        """
        data = await repo.get_accounting_summary(session)
        logger.debug(
            "Accounting summary assembled",
            active_lots=data["portfolio_active_lots"],
            open_exposure=data["open_exposure"],
            available=data["spendable_available_capital"],
        )
        return data

    async def get_pnl_summary(self, session: AsyncSession) -> dict:
        """
        PnL aggregates: unrealized from OPEN positions, realized from CLOSED.

        Returns
        -------
        dict matching PnlSummaryResponse schema.
        """
        data = await repo.get_pnl_summary(session)
        logger.debug(
            "PnL summary assembled",
            open_positions=data["open_positions"],
            total_unrealized_pnl=data["total_unrealized_pnl"],
        )
        return data
