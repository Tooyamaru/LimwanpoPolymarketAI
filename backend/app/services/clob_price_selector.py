"""
Exact-Side CLOB Price Selector — Checkpoint 14A1.

Provides a single pure helper that selects the executable price for a given
side (YES / NO) and action (BUY / SELL / MARK) from a canonical
ClobMarketData snapshot.

Price semantics (non-negotiable):

    YES + BUY  → yes_ask       (cost to enter a YES position)
    YES + SELL → yes_bid       (proceeds from exiting a YES position)
    YES + MARK → yes_mid       (mark-to-market for YES)

    NO  + BUY  → no_ask        (cost to enter a NO position)
    NO  + SELL → no_bid        (proceeds from exiting a NO position)
    NO  + MARK → no_mid        (mark-to-market for NO)

Complement fallback is PERMANENTLY FORBIDDEN:

    ✗  1 - yes_bid   as NO ask
    ✗  1 - yes_ask   as NO bid
    ✗  1 - yes_mid   as NO mark
    ✗  synthetic 0.5 for any side

If the required exact token-side price is missing, invalid, or the snapshot
is stale the selector returns valid=False with an explicit validation_error.
It never fabricates a fill and never mutates the snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict

from app.services.clob_client import ClobMarketData

# Default maximum age (seconds) before a snapshot is considered stale.
_DEFAULT_MAX_AGE_SECONDS: float = 60.0

# Valid price range — Polymarket probability tokens are strictly between 0 and 1.
_PRICE_MIN: float = 0.0
_PRICE_MAX: float = 1.0

_VALID_SIDES = frozenset({"YES", "NO"})
_VALID_ACTIONS = frozenset({"BUY", "SELL", "MARK"})


class ExactPriceResult(TypedDict):
    """Structured result returned by select_exact_clob_price."""
    valid: bool
    price: Optional[float]
    token_id: Optional[str]
    source_field: Optional[str]
    validation_error: Optional[str]


def _ok(price: float, token_id: Optional[str], source_field: str) -> ExactPriceResult:
    return ExactPriceResult(
        valid=True,
        price=price,
        token_id=token_id,
        source_field=source_field,
        validation_error=None,
    )


def _err(reason: str) -> ExactPriceResult:
    return ExactPriceResult(
        valid=False,
        price=None,
        token_id=None,
        source_field=None,
        validation_error=reason,
    )


def _validate_price(price: Optional[float], unavailable_error: str) -> Optional[str]:
    """
    Return a validation_error string if the price fails basic sanity checks,
    or None if the price is acceptable.
    """
    if price is None:
        return unavailable_error
    if not isinstance(price, (int, float)):
        return "INVALID_CLOB_PRICE"
    if price <= _PRICE_MIN or price >= _PRICE_MAX:
        return "INVALID_CLOB_PRICE"
    return None


def select_exact_clob_price(
    side: str,
    action: str,
    snapshot: ClobMarketData,
    expected_condition_id: Optional[str] = None,
    max_age_seconds: float = _DEFAULT_MAX_AGE_SECONDS,
) -> ExactPriceResult:
    """
    Select the exact executable price for the given side and action.

    Parameters
    ----------
    side:
        "YES" or "NO" — which token side to price.
    action:
        "BUY", "SELL", or "MARK" — the intended action.
    snapshot:
        A ClobMarketData snapshot (from clob_client.get_market).
    expected_condition_id:
        When provided, the snapshot's condition_id must match exactly.
        Returns CONDITION_BINDING_MISMATCH on disagreement.
    max_age_seconds:
        Snapshots with fetched_at older than this many seconds are rejected
        as stale.  Snapshots without a fetched_at are not checked.

    Returns
    -------
    ExactPriceResult with valid=True and the exact price, or valid=False with
    an explicit validation_error.  The snapshot is never mutated.
    """
    # ── Guard: side / action ──────────────────────────────────────────────────
    if side not in _VALID_SIDES:
        return _err("INVALID_SIDE")
    if action not in _VALID_ACTIONS:
        return _err("INVALID_ACTION")

    # ── Guard: condition binding mismatch ─────────────────────────────────────
    if expected_condition_id is not None:
        if snapshot.condition_id != expected_condition_id:
            return _err("CONDITION_BINDING_MISMATCH")

    # ── Guard: stale snapshot ─────────────────────────────────────────────────
    if snapshot.fetched_at is not None:
        # Ensure both datetimes are tz-aware for comparison.
        fetched = snapshot.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - fetched).total_seconds()
        if age_seconds > max_age_seconds:
            return _err("CLOB_SNAPSHOT_STALE")

    # ── YES side ──────────────────────────────────────────────────────────────
    if side == "YES":
        if not snapshot.yes_token_id:
            return _err("YES_TOKEN_ID_MISSING")

        if action == "BUY":
            err = _validate_price(snapshot.yes_ask, "YES_ASK_UNAVAILABLE")
            if err:
                return _err(err)
            # Extra cross-check: ask must be >= bid if bid is present.
            if snapshot.yes_bid is not None and snapshot.yes_ask < snapshot.yes_bid:
                return _err("INVALID_CLOB_PRICE")
            return _ok(snapshot.yes_ask, snapshot.yes_token_id, "yes_ask")  # type: ignore[arg-type]

        if action == "SELL":
            err = _validate_price(snapshot.yes_bid, "YES_BID_UNAVAILABLE")
            if err:
                return _err(err)
            if snapshot.yes_ask is not None and snapshot.yes_bid > snapshot.yes_ask:
                return _err("INVALID_CLOB_PRICE")
            return _ok(snapshot.yes_bid, snapshot.yes_token_id, "yes_bid")  # type: ignore[arg-type]

        # MARK
        err = _validate_price(snapshot.yes_mid, "YES_MID_UNAVAILABLE")
        if err:
            return _err(err)
        return _ok(snapshot.yes_mid, snapshot.yes_token_id, "yes_mid")  # type: ignore[arg-type]

    # ── NO side ───────────────────────────────────────────────────────────────
    # NOTE: NO prices come EXCLUSIVELY from the NO order book.
    # Complement calculations (1 - yes_bid, 1 - yes_ask, 1 - yes_mid)
    # are permanently forbidden.
    if not snapshot.no_token_id:
        return _err("NO_TOKEN_ID_MISSING")

    if action == "BUY":
        err = _validate_price(snapshot.no_ask, "NO_ASK_UNAVAILABLE")
        if err:
            return _err(err)
        if snapshot.no_bid is not None and snapshot.no_ask < snapshot.no_bid:
            return _err("INVALID_CLOB_PRICE")
        return _ok(snapshot.no_ask, snapshot.no_token_id, "no_ask")  # type: ignore[arg-type]

    if action == "SELL":
        err = _validate_price(snapshot.no_bid, "NO_BID_UNAVAILABLE")
        if err:
            return _err(err)
        if snapshot.no_ask is not None and snapshot.no_bid > snapshot.no_ask:
            return _err("INVALID_CLOB_PRICE")
        return _ok(snapshot.no_bid, snapshot.no_token_id, "no_bid")  # type: ignore[arg-type]

    # MARK
    err = _validate_price(snapshot.no_mid, "NO_MID_UNAVAILABLE")
    if err:
        return _err(err)
    return _ok(snapshot.no_mid, snapshot.no_token_id, "no_mid")  # type: ignore[arg-type]
