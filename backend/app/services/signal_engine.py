"""
Signal Engine — Layer 4.

Scans the two most recent market_price_snapshots for each active universe
market and emits structured signals when meaningful price events are detected.

Signal types (calibrated from Audit #1-#5 empirical findings):

  MID_MOVE
    Triggered when yes_mid changes by > MID_MOVE_THRESHOLD between
    consecutive 10-second snapshots.

  SEED_DEVIATION
    Triggered when abs(yes_mid - 0.50) >= SEED_DEVIATION_THRESHOLD.
    All markets seed at 0.50; any meaningful deviation means a trade
    has consumed depth and pushed the market away from its seed.

  SPREAD_CHANGE
    Triggered when the spread changes by >= SPREAD_CHANGE_THRESHOLD.

Severity tiers:
  LOW    |delta| < 0.01 or deviation 0.01–0.02
  MEDIUM |delta| in [0.01, 0.05) or deviation 0.02–0.05
  HIGH   |delta| >= 0.05 or deviation >= 0.05

Phase 1 AI additions (see signal_confidence.py):
  confidence_score  — 0–100 quality score per signal
  regime            — RANGING|TRENDING_UP|TRENDING_DOWN|VOLATILE|UNKNOWN
  mtf_confirmed     — True when ≥2 timeframes for the same asset fired
                      in this scan cycle or within MTF_LOOKBACK_SECONDS

Deduplication:
  A signal is only emitted if the previous stored signal of the same type
  for the same market had a different yes_mid_after value.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.signal import Signal
from app.repositories import signal_repository as repo
from app.repositories.market_price_repository import get_latest_by_condition
from app.repositories.universe_repository import get_active_universe
from app.services.signal_confidence import compute_confidence, detect_regime

logger = get_logger(__name__)

MID_MOVE_THRESHOLD = 0.001
SEED_DEVIATION_THRESHOLD = 0.010
SPREAD_CHANGE_THRESHOLD = 0.005
SEED_PRICE = 0.50

MTF_LOOKBACK_SECONDS = 300
MTF_MIN_TIMEFRAMES = 2
REGIME_LOOKBACK_SNAPSHOTS = 10


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

    Phase 1 enhancements:
    - Computes confidence_score per signal (signal_confidence.compute_confidence)
    - Detects market regime from last N snapshots (signal_confidence.detect_regime)
    - Sets mtf_confirmed after full scan cycle if ≥2 timeframes for the same
      asset emitted signals in this cycle

    Usage (from FastAPI lifespan or background loop)::

        engine = SignalEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        """
        Run one full scan cycle across all active universe markets.

        Returns a summary dict::
            {
                "markets_scanned": int,
                "signals_emitted": int,
                "mtf_confirmed": int,
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
                "mtf_confirmed": 0,
                "skipped_no_data": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        markets_scanned = 0
        skipped_no_data = 0
        errors = 0

        # asset → list of (timeframe, [Signal objects emitted this cycle])
        asset_signals: dict[str, dict[str, list[Signal]]] = defaultdict(lambda: defaultdict(list))

        for market in active_markets:
            try:
                new_signals = await self._scan_market(session, market)
                markets_scanned += 1
                if new_signals:
                    asset_signals[market.asset][market.timeframe].extend(new_signals)
            except Exception as exc:
                logger.error(
                    "Signal engine error for market",
                    condition_id=market.condition_id[:12],
                    asset=market.asset,
                    timeframe=market.timeframe,
                    error=str(exc),
                )
                errors += 1

        # ── Multi-Timeframe Confirmation ──────────────────────────────────────
        # For each asset, check if signals fired across ≥ MTF_MIN_TIMEFRAMES
        # timeframes in this cycle.  If yes, mark all cycle signals as confirmed.
        # Also check DB for recent signals within MTF_LOOKBACK_SECONDS.
        total_signals_emitted = 0
        total_mtf_confirmed = 0

        for asset, tf_map in asset_signals.items():
            cycle_tfs = set(tf_map.keys())

            # Also check DB for recent signals on other timeframes not hit this cycle
            if len(cycle_tfs) < MTF_MIN_TIMEFRAMES:
                try:
                    recent = await repo.get_recent_signals_by_asset(
                        session, asset, lookback_seconds=MTF_LOOKBACK_SECONDS
                    )
                    db_tfs = {s.timeframe for s in recent}
                    combined_tfs = cycle_tfs | db_tfs
                except Exception:
                    combined_tfs = cycle_tfs
            else:
                combined_tfs = cycle_tfs

            is_mtf = len(combined_tfs) >= MTF_MIN_TIMEFRAMES

            for tf, signals in tf_map.items():
                for sig in signals:
                    total_signals_emitted += 1
                    if is_mtf and not sig.mtf_confirmed:
                        sig.mtf_confirmed = True
                        total_mtf_confirmed += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        if total_signals_emitted > 0:
            logger.info(
                "Signal engine scan complete",
                markets_scanned=markets_scanned,
                signals_emitted=total_signals_emitted,
                mtf_confirmed=total_mtf_confirmed,
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
            "signals_emitted": total_signals_emitted,
            "mtf_confirmed": total_mtf_confirmed,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _scan_market(
        self,
        session: AsyncSession,
        market: MarketUniverse,
    ) -> list[Signal]:
        """
        Compare the latest snapshots for one market.
        Returns list of Signal objects emitted in this cycle.
        """
        snapshots = await get_latest_by_condition(
            session, market.condition_id, limit=REGIME_LOOKBACK_SNAPSHOTS
        )

        if len(snapshots) < 2:
            return []

        # snapshots[0] = newest, snapshots[-1] = oldest (chronological for regime)
        newer = snapshots[0]
        older = snapshots[1]

        mid_after = newer.yes_mid
        mid_before = older.yes_mid
        spread_after = newer.spread_yes
        spread_before = older.spread_yes

        if mid_after is None or mid_before is None:
            return []

        mid_delta = round(mid_after - mid_before, 8)
        abs_mid_delta = abs(mid_delta)
        deviation = round(abs(mid_after - SEED_PRICE), 8)

        spread_delta: Optional[float] = None
        if spread_after is not None and spread_before is not None:
            spread_delta = round(spread_after - spread_before, 8)

        # Compute regime from all available snapshots (oldest→newest)
        mids_chrono = [
            s.yes_mid for s in reversed(snapshots) if s.yes_mid is not None
        ]
        regime = detect_regime(mids_chrono)

        kwargs = dict(
            condition_id=market.condition_id,
            asset=market.asset,
            timeframe=market.timeframe,
            snapshot_id_before=older.id,
            snapshot_id_after=newer.id,
        )

        emitted: list[Signal] = []

        if abs_mid_delta > MID_MOVE_THRESHOLD:
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "MID_MOVE"
            )
            if last is None or last.yes_mid_after != mid_after:
                severity = _compute_severity_mid(mid_delta)
                confidence = compute_confidence(
                    signal_type="MID_MOVE",
                    severity=severity,
                    yes_mid_delta=mid_delta,
                    spread_after=spread_after,
                )
                sig = await repo.save_signal(
                    session,
                    signal_type="MID_MOVE",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    severity=severity,
                    confidence_score=confidence,
                    regime=regime,
                    mtf_confirmed=False,
                    **kwargs,
                )
                emitted.append(sig)

        if deviation >= SEED_DEVIATION_THRESHOLD:
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "SEED_DEVIATION"
            )
            if last is None or last.yes_mid_after != mid_after:
                severity = _compute_severity_deviation(deviation)
                confidence = compute_confidence(
                    signal_type="SEED_DEVIATION",
                    severity=severity,
                    seed_deviation=deviation,
                    spread_after=spread_after,
                )
                sig = await repo.save_signal(
                    session,
                    signal_type="SEED_DEVIATION",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    seed_deviation=deviation,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    severity=severity,
                    confidence_score=confidence,
                    regime=regime,
                    mtf_confirmed=False,
                    **kwargs,
                )
                emitted.append(sig)

        if (
            spread_delta is not None
            and abs(spread_delta) >= SPREAD_CHANGE_THRESHOLD
        ):
            last = await repo.get_last_signal_for_market(
                session, market.condition_id, "SPREAD_CHANGE"
            )
            if last is None or last.spread_after != spread_after:
                severity = _compute_severity_spread(spread_delta)
                confidence = compute_confidence(
                    signal_type="SPREAD_CHANGE",
                    severity=severity,
                    yes_mid_delta=mid_delta,
                    spread_after=spread_after,
                )
                sig = await repo.save_signal(
                    session,
                    signal_type="SPREAD_CHANGE",
                    yes_mid_before=mid_before,
                    yes_mid_after=mid_after,
                    yes_mid_delta=mid_delta,
                    spread_before=spread_before,
                    spread_after=spread_after,
                    spread_delta=spread_delta,
                    severity=severity,
                    confidence_score=confidence,
                    regime=regime,
                    mtf_confirmed=False,
                    **kwargs,
                )
                emitted.append(sig)

        return emitted
