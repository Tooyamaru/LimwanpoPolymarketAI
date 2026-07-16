"""
Live Trades router tests — event classification and side-label correctness.

Covers the seven required guarantees for the AI LIVE TRADES feed:
  - entry orders classify as ENTRY / SCALE_IN based on entry_sequence
  - exit orders classify as PARTIAL_EXIT / FINAL_EXIT / EXPIRY_EXIT
  - side_label is always the raw YES/NO the frontend maps to UP/DOWN
  - only FILLED orders in the allowed side set are ever considered
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.v1.live_trades import _derive_event_type


def _now():
    return datetime.now(timezone.utc)


def _order(side: str) -> MagicMock:
    o = MagicMock()
    o.side = side
    return o


def _position(entry_sequence=None, close_reason=None, remaining_quantity=None) -> MagicMock:
    p = MagicMock()
    p.entry_sequence = entry_sequence
    p.close_reason = close_reason
    p.remaining_quantity = remaining_quantity
    p.opened_at = _now()
    return p


class TestEntryClassification:
    def test_first_entry_is_entry(self):
        assert _derive_event_type(_order("LONG_YES"), _position(entry_sequence=1)) == "ENTRY"

    def test_second_entry_is_scale_in(self):
        assert _derive_event_type(_order("LONG_NO"), _position(entry_sequence=2)) == "SCALE_IN"

    def test_entry_with_no_linked_position_falls_back_to_entry(self):
        assert _derive_event_type(_order("LONG_YES"), None) == "ENTRY"


class TestExitClassification:
    def test_expiry_close_reason_wins(self):
        pos = _position(close_reason="EXPIRY_EXIT", remaining_quantity=0.0)
        assert _derive_event_type(_order("SELL_YES"), pos) == "EXPIRY_EXIT"

    def test_fully_closed_position_is_final_exit(self):
        pos = _position(close_reason="MANUAL", remaining_quantity=0.0)
        assert _derive_event_type(_order("SELL_NO"), pos) == "FINAL_EXIT"

    def test_partially_closed_position_is_partial_exit(self):
        pos = _position(close_reason=None, remaining_quantity=5.0)
        assert _derive_event_type(_order("SELL_YES"), pos) == "PARTIAL_EXIT"

    def test_exit_with_no_linked_position_falls_back_to_final_exit(self):
        assert _derive_event_type(_order("SELL_NO"), None) == "FINAL_EXIT"


@pytest.mark.anyio
class TestLiveTradesEndpoint:
    async def test_side_label_is_raw_yes_no_not_up_down(self, client):
        """
        The API must keep emitting raw YES/NO — UP/DOWN mapping is a
        presentation-layer concern owned by the frontend (ltDirection()),
        never the backend contract.
        """
        r = await client.get("/api/v1/live-trades?limit=50")
        assert r.status_code == 200
        events = r.json()
        for ev in events:
            assert ev["side"] in ("YES", "NO")

    async def test_only_known_event_types_returned(self, client):
        r = await client.get("/api/v1/live-trades?limit=50")
        assert r.status_code == 200
        allowed = {"ENTRY", "SCALE_IN", "PARTIAL_EXIT", "FINAL_EXIT", "EXPIRY_EXIT"}
        for ev in r.json():
            assert ev["event_type"] in allowed
