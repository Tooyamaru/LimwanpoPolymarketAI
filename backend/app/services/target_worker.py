"""
Target Worker — fetches official Price to Beat for each active market.

Priority order (per spec §9):
  1. Official Polymarket field from Gamma API event response:
       priceToBeat, price_to_beat, initialValue, initial_value,
       referencePrice, reference_price, openPrice, open_price,
       oraclePrice, oracle_price  (checked in this order)
     → target_verified=True, target_source="POLYMARKET_GAMMA"

  2. No official field found in Gamma API response
     → target_price remains None, target_verified=False
     → Status: TARGET PENDING — entry blocked by integrity gate
     → Note: the Gamma API field investigation result is logged

Design decisions:
  - Immutable once locked: if target_verified=True, the row is never updated again.
  - Only writes when target is None or unverified — never overwrites a verified target.
  - On every cycle, unverified markets are retried so that fields added later
    by Polymarket are eventually picked up.
  - Uses create_verified_httpx_client() for all outbound HTTPS calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
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


class TargetWorker:
    """
    Periodic worker that resolves the official Price to Beat for every
    active market that does not yet have target_verified=True.
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

        async with create_verified_httpx_client() as http:
            for market in pending:
                try:
                    result = await self._resolve_one(http, market)
                    if result:
                        verified += 1
                        await self._persist_verified(session, market, result)
                    else:
                        still_pending += 1
                        await self._persist_pending(session, market)
                except Exception as exc:
                    errors += 1
                    logger.warning(
                        "[TARGET] Resolution error",
                        condition_id=market.condition_id[:12],
                        asset=market.asset,
                        error=str(exc),
                    )

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
        Try to find the official Price to Beat for *market* in the Gamma API.

        Returns a result dict on success, None when no official field exists.
        """
        event_slug = market.event_slug
        condition_id = market.condition_id

        if not event_slug:
            logger.debug(
                "[TARGET] No event_slug — cannot query Gamma",
                condition_id=condition_id[:12],
            )
            return None

        # ── Gamma API probe ────────────────────────────────────────────────
        try:
            resp = await http.get(
                GAMMA_EVENTS_URL,
                params={"slug": event_slug},
                timeout=10.0,
            )
            resp.raise_for_status()
            events: list[dict] = resp.json() if isinstance(resp.json(), list) else [resp.json()]
        except Exception as exc:
            logger.warning(
                "[TARGET] Gamma API request failed",
                event_slug=event_slug,
                error=str(exc),
            )
            return None

        # ── Field search ──────────────────────────────────────────────────
        # Look in both the event-level and each nested market object.
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
                # Only look at the matching condition_id if available
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
            }

        # ── No official field found ────────────────────────────────────────
        logger.debug(
            "[TARGET] No official Price to Beat field in Gamma API response",
            asset=market.asset,
            event_slug=event_slug,
            condition_id=condition_id[:12],
            candidates_checked=_CANDIDATE_FIELDS,
        )
        return None

    async def _persist_verified(
        self, session, market: MarketUniverse, result: dict
    ) -> None:
        """Write a verified target to the DB (immutable once locked)."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == market.condition_id,
                MarketUniverse.target_verified == False,  # noqa: E712 — SQLAlchemy filter
            )
            .values(
                target_price=result["target_price"],
                target_source=result["target_source"],
                target_raw_source=result["target_raw_source"],
                target_event_slug=result["target_event_slug"],
                target_condition_id=result["target_condition_id"],
                target_verified=True,
                target_stale=False,
                target_locked_at=now,
                target_source_timestamp=now,
                target_validation_error=None,
                updated_at=now,
            )
        )
        result_obj = await session.execute(stmt)
        if result_obj.rowcount > 0:
            logger.info(
                "[TARGET] Target locked",
                asset=market.asset,
                condition_id=market.condition_id[:12],
                target_price=result["target_price"],
                source=result["target_source"],
            )
        else:
            logger.debug(
                "[TARGET] Target already locked — skipped",
                condition_id=market.condition_id[:12],
            )
        await session.flush()

    async def _persist_pending(self, session, market: MarketUniverse) -> None:
        """
        Mark a market as still PENDING (no official field found).

        Does NOT overwrite a previously verified target.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(MarketUniverse)
            .where(
                MarketUniverse.condition_id == market.condition_id,
                MarketUniverse.target_verified == False,  # noqa: E712
            )
            .values(
                target_stale=True,
                target_validation_error="No official Price to Beat field in Gamma API",
                updated_at=now,
            )
        )
        await session.execute(stmt)
        await session.flush()
