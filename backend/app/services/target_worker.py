"""
Target Worker — fetches official Price to Beat for each active market.

Priority order (per spec §2/§5):
  1. Official Polymarket field from Gamma API event response:
       priceToBeat, price_to_beat, initialValue, initial_value,
       referencePrice, reference_price, openPrice, open_price,
       oraclePrice, oracle_price  (checked in this order)
     → target_verified=True, target_source="POLYMARKET_GAMMA"

  2. Gamma API found nothing AND a Chainlink RTDS tick exists at or before
     prediction_window_start (within CHAINLINK_PRESTART_LOOKBACK_SECONDS):
     → target_price = Chainlink candidate value (stored for diagnostics only)
     → target_source = "CHAINLINK_PRESTART_CANDIDATE"
     → target_verified = False
     → target_validation_error = "OFFICIAL_PRICE_TO_BEAT_NOT_RECONCILED"
     → target_candidate_rule = "tick_at_or_before" | "none_available"
     Entry remains BLOCKED until official reconciliation succeeds.

  3. No official field and no usable Chainlink tick:
     → target_price = None, target_verified = False
     → target_validation_error = "No official Price to Beat field in Gamma API"
     → target_candidate_rule = "none_available"

Design decisions:
  - Immutable once locked: if target_verified=True, the row is never updated again.
  - Only writes when target_verified IS FALSE — never overwrites a verified target.
  - Snapshot guard: before committing a result for condition_id=X, the worker
    re-checks that X is still the active market.  A delayed result from a
    previous window cannot write into a new one (spec §7).
  - Retry bookkeeping: target_retry_count, target_last_attempt_at,
    target_next_attempt_at, target_last_error are updated on every cycle.
  - Uses create_verified_httpx_client() for all outbound HTTPS calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.services.chainlink_client import get_chainlink_client
from app.services.http_client import create_verified_httpx_client

logger = get_logger(__name__)

GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

# Official Price to Beat field names to probe, in priority order.
_CANDIDATE_FIELDS = [
    "priceToBeat",
    "price_to_beat",
    "initialValue",
    "initial_value",
    "referencePrice",
    "reference_price",
    "openPrice",
    "open_price",
    "oraclePrice",
    "oracle_price",
]

# Maximum seconds before prediction_window_start that a Chainlink tick is
# considered a valid pre-start candidate.  5 minutes = 300 s.
_CHAINLINK_PRESTART_LOOKBACK_SECONDS = 300

# Minimum retry interval between target-worker attempts for the same market.
# Ensures we don't hammer Gamma on every 10-second engine cycle.
_RETRY_MIN_INTERVAL_SECONDS = 30


class TargetWorker:
    """
    Periodic worker that resolves the official Price to Beat for every
    active market that does not yet have target_verified=True.

    Also stores a Chainlink RTDS candidate for diagnostics when the official
    Gamma API field is absent.  The candidate is NEVER auto-verified — it
    remains target_verified=False until official reconciliation succeeds.
    """

    async def run_once(self, session) -> dict:
        """
        Execute one full resolution cycle.

        Returns a summary dict with counts of markets processed.
        """
        from app.repositories.universe_repository import get_active_universe

        markets = await get_active_universe(session)
        pending = [m for m in markets if not m.target_verified]

        if not pending:
            logger.debug("[TARGET] No unverified markets — skipping cycle")
            return {"checked": 0, "verified": 0, "still_pending": 0, "errors": 0}

        verified = 0
        still_pending = 0
        errors = 0
        now = datetime.now(timezone.utc)

        async with create_verified_httpx_client() as http:
            for market in pending:
                # Rate-limit: skip if last attempt was too recent.
                if (
                    market.target_last_attempt_at is not None
                    and (now - market.target_last_attempt_at).total_seconds()
                    < _RETRY_MIN_INTERVAL_SECONDS
                    and market.target_retry_count > 0
                ):
                    logger.debug(
                        "[TARGET] Rate-limited — skipping",
                        condition_id=market.condition_id[:12],
                        retry_count=market.target_retry_count,
                    )
                    still_pending += 1
                    continue

                try:
                    result = await self._resolve_one(http, market)
                    if result and result.get("target_verified"):
                        verified += 1
                        await self._persist_verified(session, market, result, now)
                    else:
                        still_pending += 1
                        await self._persist_pending(session, market, result, now)
                except Exception as exc:
                    errors += 1
                    logger.warning(
                        "[TARGET] Resolution error",
                        condition_id=market.condition_id[:12],
                        asset=market.asset,
                        error=str(exc),
                    )
                    await self._persist_error(session, market, str(exc), now)

        await session.commit()
        logger.info(
            "[TARGET] Cycle complete",
            checked=len(pending),
            verified=verified,
            still_pending=still_pending,
            errors=errors,
        )
        return {
            "checked": len(pending),
            "verified": verified,
            "still_pending": still_pending,
            "errors": errors,
        }

    async def _resolve_one(
        self, http, market: MarketUniverse
    ) -> Optional[dict]:
        """
        Try to find the official Price to Beat for *market*.

        Priority 1: Gamma API official field → returns verified result.
        Priority 2: Chainlink RTDS candidate (unverified, diagnostic only).
        Priority 3: Neither available → returns pending result.
        """
        event_slug = market.event_slug
        condition_id = market.condition_id

        # ── Priority 1: Gamma API ─────────────────────────────────────────────
        gamma_result = await self._probe_gamma(http, market)
        if gamma_result is not None:
            return gamma_result

        # ── Priority 2: Chainlink RTDS candidate (diagnostic, NOT verified) ──
        chainlink_result = self._probe_chainlink_candidate(market)
        if chainlink_result is not None:
            logger.info(
                "[TARGET] Chainlink candidate stored (unverified — entry blocked)",
                asset=market.asset,
                condition_id=condition_id[:12],
                candidate_value=chainlink_result.get("target_price"),
                candidate_rule=chainlink_result.get("target_candidate_rule"),
            )
            return chainlink_result

        # ── Priority 3: Nothing available ────────────────────────────────────
        return None

    async def _probe_gamma(
        self, http, market: MarketUniverse
    ) -> Optional[dict]:
        """
        Query the Gamma API for an official priceToBeat / initialValue field.

        Returns a verified result dict on success, None otherwise.
        """
        event_slug = market.event_slug
        condition_id = market.condition_id

        if not event_slug:
            logger.debug(
                "[TARGET] No event_slug — cannot query Gamma",
                condition_id=condition_id[:12],
            )
            return None

        try:
            resp = await http.get(
                GAMMA_EVENTS_URL,
                params={"slug": event_slug},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            events: list[dict] = data if isinstance(data, list) else [data]
        except Exception as exc:
            logger.warning(
                "[TARGET] Gamma API request failed",
                event_slug=event_slug,
                error=str(exc),
            )
            return None

        found_field: Optional[str] = None
        found_value: Optional[float] = None
        found_raw: Optional[str] = None

        for event in events:
            # Check event-level fields first
            for field_name in _CANDIDATE_FIELDS:
                raw = event.get(field_name)
                if raw is not None:
                    try:
                        val = float(raw)
                        if val > 0:
                            found_field = field_name
                            found_value = val
                            found_raw = str(raw)
                            break
                    except (TypeError, ValueError):
                        pass
            if found_field:
                break

            # Then check nested markets array
            for m_data in event.get("markets", []):
                if not isinstance(m_data, dict):
                    continue
                m_cid = m_data.get("conditionId") or m_data.get("condition_id")
                if m_cid and m_cid != condition_id:
                    continue
                for field_name in _CANDIDATE_FIELDS:
                    raw = m_data.get(field_name)
                    if raw is not None:
                        try:
                            val = float(raw)
                            if val > 0:
                                found_field = field_name
                                found_value = val
                                found_raw = str(raw)
                                break
                        except (TypeError, ValueError):
                            pass
                if found_field:
                    break
            if found_field:
                break

        if found_field is not None and found_value is not None:
            logger.info(
                "[TARGET] Official Price to Beat found",
                asset=market.asset,
                event_slug=event_slug,
                field=found_field,
                value=found_value,
                condition_id=condition_id[:12],
            )
            return {
                "target_price": found_value,
                "target_source": "POLYMARKET_GAMMA",
                "target_raw_source": f"{event_slug}/{found_field}={found_raw}",
                "target_event_slug": event_slug,
                "target_condition_id": condition_id,
                "target_verified": True,
                "target_candidate_rule": found_field,
                "target_validation_error": None,
            }

        logger.debug(
            "[TARGET] No official Price to Beat field in Gamma API response",
            asset=market.asset,
            event_slug=event_slug,
            condition_id=condition_id[:12],
            candidates_checked=_CANDIDATE_FIELDS,
        )
        return None

    def _probe_chainlink_candidate(
        self, market: MarketUniverse
    ) -> Optional[dict]:
        """
        Look for a Chainlink RTDS tick at or before prediction_window_start.

        Returns an UNVERIFIED candidate dict (target_verified=False) when a
        tick is found within CHAINLINK_PRESTART_LOOKBACK_SECONDS of the window
        start.  Returns None when no tick is available.

        IMPORTANT: This candidate is stored for diagnostics ONLY.
        target_verified remains False — entry is blocked until the official
        Gamma API field is confirmed.
        """
        client = get_chainlink_client()
        if client is None:
            return None

        pw_start = market.prediction_window_start
        if pw_start is None:
            return None

        pw_start_ms = int(pw_start.timestamp() * 1000)
        lookback_ms = pw_start_ms - (_CHAINLINK_PRESTART_LOOKBACK_SECONDS * 1000)

        # Try: latest tick at or before window_start
        tick = client.get_tick_at_or_before(market.asset, pw_start_ms)

        if tick is None:
            logger.debug(
                "[TARGET] No Chainlink tick at/before window start",
                asset=market.asset,
                pw_start_ms=pw_start_ms,
            )
            return {
                "target_price": None,
                "target_source": "CHAINLINK_PRESTART_CANDIDATE",
                "target_raw_source": None,
                "target_event_slug": market.event_slug,
                "target_condition_id": market.condition_id,
                "target_verified": False,
                "target_candidate_rule": "none_available",
                "target_validation_error": "OFFICIAL_PRICE_TO_BEAT_NOT_RECONCILED",
            }

        # Only accept ticks within the lookback window
        if tick.source_ts_ms < lookback_ms:
            logger.debug(
                "[TARGET] Nearest Chainlink tick too old for candidate",
                asset=market.asset,
                tick_age_s=(pw_start_ms - tick.source_ts_ms) / 1000,
            )
            return {
                "target_price": None,
                "target_source": "CHAINLINK_PRESTART_CANDIDATE",
                "target_raw_source": None,
                "target_event_slug": market.event_slug,
                "target_condition_id": market.condition_id,
                "target_verified": False,
                "target_candidate_rule": "none_available",
                "target_validation_error": "OFFICIAL_PRICE_TO_BEAT_NOT_RECONCILED",
            }

        delta_s = (pw_start_ms - tick.source_ts_ms) / 1000

        logger.debug(
            "[TARGET] Chainlink candidate tick found",
            asset=market.asset,
            tick_value=tick.value,
            tick_rule="tick_at_or_before",
            delta_s=round(delta_s, 1),
        )

        return {
            "target_price": tick.value,
            "target_source": "CHAINLINK_PRESTART_CANDIDATE",
            "target_raw_source": (
                f"{market.asset}/chainlink/{tick.source_ts_ms}"
                f"/delta={round(delta_s, 1)}s"
            ),
            "target_event_slug": market.event_slug,
            "target_condition_id": market.condition_id,
            "target_verified": False,
            "target_candidate_rule": "tick_at_or_before",
            "target_validation_error": "OFFICIAL_PRICE_TO_BEAT_NOT_RECONCILED",
        }

    async def _persist_verified(
        self,
        session,
        market: MarketUniverse,
        result: dict,
        now: datetime,
    ) -> None:
        """
        Write a verified target to the DB (immutable once locked).

        Snapshot guard: verifies the market is still the active market for its
        (asset, timeframe) before writing.  A delayed result from a previous
        prediction window cannot contaminate the current one.
        """
        condition_id = market.condition_id

        # Snapshot guard — re-check that this condition is still the active market.
        if not await self._is_still_active(session, condition_id):
            logger.warning(
                "[TARGET] Snapshot guard triggered — condition no longer active; "
                "discarding stale result",
                condition_id=condition_id[:12],
                asset=market.asset,
            )
            return

        retry_count = (market.target_retry_count or 0) + 1
        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == condition_id,
                MarketUniverse.target_verified == False,  # noqa: E712
            )
            .values(
                target_price=result["target_price"],
                target_source=result["target_source"],
                target_raw_source=result.get("target_raw_source"),
                target_event_slug=result.get("target_event_slug"),
                target_condition_id=result.get("target_condition_id"),
                target_verified=True,
                target_stale=False,
                target_locked_at=now,
                target_source_timestamp=now,
                target_validation_error=None,
                target_candidate_rule=result.get("target_candidate_rule"),
                target_retry_count=retry_count,
                target_last_attempt_at=now,
                target_next_attempt_at=None,
                target_last_error=None,
                updated_at=now,
            )
        )
        result_obj = await session.execute(stmt)
        if result_obj.rowcount > 0:
            logger.info(
                "[TARGET] Target locked",
                asset=market.asset,
                condition_id=condition_id[:12],
                target_price=result["target_price"],
                source=result["target_source"],
                retry_count=retry_count,
            )
        else:
            logger.debug(
                "[TARGET] Target already locked — skipped",
                condition_id=condition_id[:12],
            )
        await session.flush()

    async def _persist_pending(
        self,
        session,
        market: MarketUniverse,
        result: Optional[dict],
        now: datetime,
    ) -> None:
        """
        Persist a pending / unverified state.

        When result contains a Chainlink candidate value, it is stored for
        diagnostics but target_verified remains False.
        """
        retry_count = (market.target_retry_count or 0) + 1
        next_attempt = now + timedelta(seconds=_RETRY_MIN_INTERVAL_SECONDS)

        values: dict = {
            "target_stale": True,
            "target_retry_count": retry_count,
            "target_last_attempt_at": now,
            "target_next_attempt_at": next_attempt,
            "updated_at": now,
        }

        if result is not None:
            values["target_validation_error"] = result.get(
                "target_validation_error",
                "No official Price to Beat field in Gamma API",
            )
            values["target_candidate_rule"] = result.get("target_candidate_rule")
            # Store candidate price/source for diagnostics (target_verified stays False)
            if result.get("target_price") is not None:
                values["target_price"] = result["target_price"]
                values["target_source"] = result["target_source"]
                values["target_raw_source"] = result.get("target_raw_source")
        else:
            values["target_validation_error"] = (
                "No official Price to Beat field in Gamma API"
            )
            values["target_candidate_rule"] = "none_available"

        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == market.condition_id,
                MarketUniverse.target_verified == False,  # noqa: E712
            )
            .values(**values)
        )
        await session.execute(stmt)
        await session.flush()

    async def _persist_error(
        self,
        session,
        market: MarketUniverse,
        error_msg: str,
        now: datetime,
    ) -> None:
        """Record a resolution error without changing verified state."""
        retry_count = (market.target_retry_count or 0) + 1
        next_attempt = now + timedelta(seconds=_RETRY_MIN_INTERVAL_SECONDS)
        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == market.condition_id,
                MarketUniverse.target_verified == False,  # noqa: E712
            )
            .values(
                target_stale=True,
                target_last_error=error_msg[:512],
                target_retry_count=retry_count,
                target_last_attempt_at=now,
                target_next_attempt_at=next_attempt,
                updated_at=now,
            )
        )
        await session.execute(stmt)
        await session.flush()

    @staticmethod
    async def _is_still_active(session, condition_id: str) -> bool:
        """
        Snapshot guard: return True if condition_id is still status='active'.

        Called before writing a verified target to prevent stale-worker results
        from Window A contaminating Window B after rollover.
        """
        from app.repositories.universe_repository import get_active_universe

        active = await get_active_universe(session)
        return any(m.condition_id == condition_id for m in active)
