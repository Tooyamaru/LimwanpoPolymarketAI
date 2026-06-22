"""
Signal Engine — Layer 4.

Scans the two most recent market_price_snapshots for each active universe
market and emits structured signals when meaningful price events are detected.

Signal types (calibrated from Audit #1-#5 empirical findings):

  MID_MOVE
    Triggered when yes_mid changes by > MID_MOVE_THRESHOLD between
    consecutive 10-second snapshots.
    Audit finding: occurs ~1 per 30 min per market at most.

  SEED_DEVIATION
    Triggered when abs(yes_mid - 0.50) >= SEED_DEVIATION_THRESHOLD.
    All markets seed at 0.50; any meaningful deviation means a trade
    has consumed depth and pushed the market away from its seed.
    Audit finding: observed in ETH/15m moving to 0.495.

  SPREAD_CHANGE
    Triggered when the spread changes by >= SPREAD_CHANGE_THRESHOLD.
    Can indicate LP withdrawal (depth-drop batch) or a fill.

Severity tiers:
  LOW    |delta| < 0.01 or deviation 0.01–0.02
  MEDIUM |delta| in [0.01, 0.05) or deviation 0.02–0.05
  HIGH   |delta| >= 0.05 or deviation >= 0.05

Deduplication:
  A signal is only emitted if the previous stored signal of the same type
  for the same market had a different yes_mid_after value. This prevents
  re-emitting the same state on every poll cycle when the price is static.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.services import signal_repository as repo
from app.services.market_price_repository import get_latest_by_condition
from app.services.universe_repository import get_active_universe

logger = get_logger(__name__)

MID_MOVE_THRESHOLD = 0.001
SEED_DEVIATION_THRESHOLD = 0.010
SPREAD_CHANGE_THRESHOLD = 0.005
SEED_PRICE = 0.50


def _compute_severity_mid(delta: float) -> str:
    abs_delta = abs(delta)
    if abs_delta >= 0.05:
        return "HIGH"
    if abs_delta >= 0.01:
        return "MEDIUM"
    return "LOW"


def _compute_severity_deviation(deviation: float) -> str:
    if deviation >= 0.05:
        return "HIGH"
    if deviation >= 0.02:
        return "MEDIUM"
    return "LOW"


def _compute_severity_spread(delta: float) -> str:
    abs_delta = abs(delta)
    if abs_delta >= 0.02:
        return "HIGH"
    if abs_delta >= 0.01:
        return "MEDIUM"
    return "LOW"


class SignalEngine:
    """
    Detects price signals by comparing consecutive CLOB snapshots.

    Usage (from FastAPI lifespan or background loop)::

        engine = SignalEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        """
        Run one full scan cycle across all active universe markets.

        Returns a summary dict:
            {
                "markets_scanned": int,
                "signals_emitted": int,
                "skipped_no_data": int,
                "errors": int,
                "duration_ms": int,
            }
        """
        started = datetime.now(timezone.utc)
        active_markets: list[MarketUniverse] = await get_active_universe(session)

        if not active_markets:
            logger.debug("Signal engine: no active markets, scan skipped")
            return {
                "markets_scanned": 0,
                "signals_emitted": 0,
                "skipped_no_data": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        markets_scanned = 0
        signals_emitted = 0
        skipped_no_data = 0
        errors = 0

        for market in active_markets:
            try:
                count = await self._scan_market(session, market)
                signals_emitted += count
                markets_scanned += 1
            except Exception as exc:
                logger.error(
                    "Signal engine error for market",
                    condition_id=market.condition_id[:12],
                    asset=market.asset,
                    timeframe=market.timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        if signals_emitted > 0:
            logger.info(
                "Signal engine scan complete",
                markets_scanned=markets_scanned,
                signals_emitted=signals_emitted,
                errors=errors,
                duration_ms=elapsed_ms,
            )
        else:
            logger.debug(
                "Signal engine scan complete (no signals)",
                markets_scanned=markets_scanned,
                duration_ms=elapsed_ms,
            )

        return {
            "markets_scanned": markets_scanned,
            "signals_emitted": signals_emitted,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _scan_market(
        self,
        session: AsyncSession,
        market: MarketUniverse,
    ) -> int:
        """
        Compare the two latest snapshots for one market.
        Returns the count of signals emitted.
        """
        snapshots = await get_latest_by_condition(
            session, market.condition_id, limit=2
        )

        if len(snapshots) < 2:
            return 0

        newer = snapshots[0]
        older = snapshots[1]

        emitted = 0

        mid_after = newer.yes_mid
        mid_before = older.yes_mid
        spread_after = newer.spread_yes
        spread_before = older.spread_yes

        if mid_after is None or mid_before is None:
            return 0

        mid_delta = round(mid_after - mid_before, 8)
        abs_mid_delta = abs(mid_delta)

        deviation = round(abs(mid_after - SEED_PRICE), 8)

        spread_delta: Optional[float] = None
        if spread_after is not None and spread_before is not None:
            spread_delta = round(spread_after - spread_before, 8)

        kwargs = dict(
            condition_id=market.condition_id,
            asset=market.asset,
            timeframe=market.timeframe,
            snapshot_id_before=older.id,
            snapshot_id_after=newer.id,
        )

        if abs_mid_delta > MID_MOVE_THRESHOLD:
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "MID_MOVE"
            )
            if last is None or last.yes_mid_after != mid_after:
                await repo.save_signal(
                    session,
                    signal_type="MID_MOVE",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    severity=_compute_severity_mid(mid_delta),
                    **kwargs,
                )
                emitted += 1

        if deviation >= SEED_DEVIATION_THRESHOLD:
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "SEED_DEVIATION"
            )
            if last is None or last.yes_mid_after != mid_after:
                await repo.save_signal(
                    session,
                    signal_type="SEED_DEVIATION",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    seed_deviation=deviation,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    severity=_compute_severity_deviation(deviation),
                    **kwargs,
                )
                emitted += 1

        if (
            spread_delta is not None
            and abs(spread_delta) >= SPREAD_CHANGE_THRESHOLD
        ):
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "SPREAD_CHANGE"
            )
            if last is None or last.spread_after != spread_after:
                await repo.save_signal(
                    session,
                    signal_type="SPREAD_CHANGE",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    spread_delta=spread_delta,
                    severity=_compute_severity_spread(spread_delta),
                    **kwargs,
                )
                emitted += 1

        return emitted
