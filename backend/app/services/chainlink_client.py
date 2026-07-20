"""
Chainlink RTDS Client — Polymarket Real-Time Data Service.

Connects to wss://ws-live-data.polymarket.com and subscribes to the
crypto_prices_chainlink topic for live Chainlink oracle prices.

Supported symbols: btc/usd, eth/usd, sol/usd, xrp/usd
Asset labels:      BTC,     ETH,     SOL,     XRP

Price source label: POLYMARKET_RTDS_CHAINLINK

Official subscription payload (v2-official):
  {
    "action": "subscribe",
    "subscriptions": [
      {"topic": "crypto_prices_chainlink", "type": "*", "filters": ""}
    ]
  }

Required application keepalive: send literal string "PING" every 5 seconds.

Validated update format:
  {
    "connection_id": "...",
    "topic": "crypto_prices_chainlink",
    "type": "update",
    "timestamp": ...,
    "payload": {
      "symbol": "btc/usd",
      "timestamp": ...,
      "value": ...,
      "full_accuracy_value": "..."
    }
  }

Architecture:
  - Singleton client; started as an asyncio task in main.py lifespan.
  - Maintains latest price per asset in memory (dict).
  - Maintains a per-asset tick deque (size: CHAINLINK_TICK_HISTORY_SIZE)
    for OHLC candle aggregation.
  - Connection states:
      connected   = WebSocket handshake succeeded
      subscribed  = official payload sent successfully
      receiving   = at least one valid update parsed
      healthy     = connected AND subscribed AND receiving AND all assets fresh
  - Reconnects automatically with CHAINLINK_RECONNECT_SECONDS delay.
  - Out-of-order / stale messages are silently discarded.

Session start is tracked so the API can expose "DATA STARTED AT <ts>"
when not enough candle history exists for the full chart window.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PRICE_SOURCE = "POLYMARKET_RTDS_CHAINLINK"

# Official subscription payload version tag
SUBSCRIPTION_PAYLOAD_VERSION = "v2-official"

# Official subscription payload — validated 2026-07-20
OFFICIAL_SUBSCRIPTION_PAYLOAD: dict = {
    "action": "subscribe",
    "subscriptions": [
        {
            "topic": "crypto_prices_chainlink",
            "type": "*",
            "filters": "",
        }
    ],
}

# Chainlink symbol → canonical asset name
SYMBOL_TO_ASSET: dict[str, str] = {
    "btc/usd": "BTC",
    "eth/usd": "ETH",
    "sol/usd": "SOL",
    "xrp/usd": "XRP",
}
ASSET_TO_SYMBOL: dict[str, str] = {v: k for k, v in SYMBOL_TO_ASSET.items()}

# Primary assets that must ALL be fresh for healthy=True
PRIMARY_ASSETS: tuple[str, ...] = ("BTC", "ETH", "SOL", "XRP")


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class ChainlinkTick:
    """A single price observation received from the RTDS feed."""

    symbol: str               # e.g. "btc/usd"
    asset: str                # e.g. "BTC"
    value: float              # Chainlink oracle price
    full_accuracy_value: str  # raw string from payload.full_accuracy_value
    source_ts_ms: int         # ms timestamp from the RTDS message
    received_at: datetime     # when this process received the tick


@dataclass
class ChainlinkPrice:
    """Snapshot of the latest known price for one asset."""

    asset: str
    symbol: str
    value: float
    full_accuracy_value: str          # raw string from RTDS payload
    source: str                       # always POLYMARKET_RTDS_CHAINLINK
    source_ts_ms: int                 # ms timestamp from the RTDS message
    received_at: datetime
    age_ms: float = 0.0
    stale: bool = False
    connected: bool = False
    subscribed: bool = False
    receiving: bool = False
    healthy: bool = False
    update_count: int = 0

    @property
    def source_ts_iso(self) -> str:
        return datetime.fromtimestamp(
            self.source_ts_ms / 1000, tz=timezone.utc
        ).isoformat()


@dataclass
class OHLCCandle:
    """Aggregated OHLC candle built from ChainlinkTick history."""

    time: int        # candle open time — Unix seconds
    open: float
    high: float
    low: float
    close: float
    tick_count: int = 0


# ── Client ────────────────────────────────────────────────────────────────────


class ChainlinkRTDSClient:
    """
    Persistent WebSocket client for Polymarket RTDS Chainlink price feed.

    Instantiate once; call ``run()`` as an asyncio task.

    Connection state definitions:
      connected   = WebSocket handshake succeeded
      subscribed  = official payload sent successfully
      receiving   = at least one valid update parsed
      healthy     = connected AND subscribed AND receiving
                    AND all primary assets (BTC/ETH/SOL/XRP) are fresh
    """

    def __init__(self) -> None:
        self._latest: dict[str, ChainlinkPrice] = {}
        self._ticks: dict[str, deque[ChainlinkTick]] = {
            asset: deque(maxlen=settings.CHAINLINK_TICK_HISTORY_SIZE)
            for asset in SYMBOL_TO_ASSET.values()
        }
        self._session_start: datetime = datetime.now(timezone.utc)

        # ── Connection state ──────────────────────────────────────────────────
        self._connected: bool = False
        self._subscribed: bool = False
        self._receiving: bool = False

        # ── Diagnostic counters / timestamps ─────────────────────────────────
        self._reconnect_count: int = 0
        self._parse_error_count: int = 0
        self._last_error: Optional[str] = None
        self._last_message_at: Optional[datetime] = None
        self._last_valid_tick_at: Optional[datetime] = None

        # ── Per-symbol state ──────────────────────────────────────────────────
        self._update_counts: dict[str, int] = {
            asset: 0 for asset in SYMBOL_TO_ASSET.values()
        }
        self._last_sequence: dict[str, int] = {}  # per-symbol latest source_ts_ms

        # ── Lifecycle ─────────────────────────────────────────────────────────
        self._stop_event: asyncio.Event = asyncio.Event()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_price(self, asset: str) -> Optional[ChainlinkPrice]:
        """Return a fresh snapshot for *asset*, or None if no data yet."""
        base = self._latest.get(asset)
        if base is None:
            return None
        now_ms = time.time() * 1000
        age_ms = now_ms - base.source_ts_ms
        stale = age_ms > (settings.CHAINLINK_STALE_SECONDS * 1000)
        return ChainlinkPrice(
            asset=base.asset,
            symbol=base.symbol,
            value=base.value,
            full_accuracy_value=base.full_accuracy_value,
            source=base.source,
            source_ts_ms=base.source_ts_ms,
            received_at=base.received_at,
            age_ms=round(age_ms),
            stale=stale,
            connected=self._connected,
            subscribed=self._subscribed,
            receiving=self._receiving,
            healthy=self._is_healthy_snapshot(),
            update_count=self._update_counts.get(asset, 0),
        )

    def get_all_prices(self) -> dict[str, ChainlinkPrice]:
        """Return fresh snapshots for all assets that have reported at least once."""
        return {
            asset: p
            for asset in SYMBOL_TO_ASSET.values()
            if (p := self.get_price(asset)) is not None
        }

    def is_healthy(self) -> bool:
        """True when connected, subscribed, receiving, and every primary asset has a fresh tick."""
        return self._is_healthy_snapshot()

    def _is_healthy_snapshot(self) -> bool:
        """Internal — compute health at the current instant."""
        if not (self._connected and self._subscribed and self._receiving):
            return False
        threshold_ms = settings.CHAINLINK_STALE_SECONDS * 1000
        now_ms = time.time() * 1000
        for asset in PRIMARY_ASSETS:
            base = self._latest.get(asset)
            if base is None:
                return False
            if (now_ms - base.source_ts_ms) > threshold_ms:
                return False
        return True

    def is_asset_fresh(self, asset: str) -> bool:
        """True when the asset has a recent (non-stale) price."""
        base = self._latest.get(asset)
        if base is None:
            return False
        age_ms = time.time() * 1000 - base.source_ts_ms
        return age_ms <= (settings.CHAINLINK_STALE_SECONDS * 1000)

    def get_ticks_since(self, asset: str, since: datetime) -> list[ChainlinkTick]:
        """Return ticks received on or after *since*."""
        since_ts = since.timestamp()
        return [
            t for t in self._ticks.get(asset, deque())
            if t.received_at.timestamp() >= since_ts
        ]

    def get_tick_at_or_before(self, asset: str, ts_ms: int) -> Optional[ChainlinkTick]:
        """
        Return the latest tick whose source_ts_ms is <= ts_ms.

        Used for Chainlink candidate lookup against a prediction_window_start
        boundary.  Returns None when no tick exists at or before that moment.
        """
        candidates = [
            t for t in self._ticks.get(asset, deque())
            if t.source_ts_ms <= ts_ms
        ]
        return max(candidates, key=lambda t: t.source_ts_ms) if candidates else None

    def get_tick_nearest(self, asset: str, ts_ms: int) -> Optional[ChainlinkTick]:
        """
        Return the tick with the smallest absolute delta to ts_ms.

        Considers ALL ticks (before and after the boundary).
        Returns None when the tick history is empty.
        """
        ticks = list(self._ticks.get(asset, deque()))
        if not ticks:
            return None
        return min(ticks, key=lambda t: abs(t.source_ts_ms - ts_ms))

    def get_ticks_window(
        self, asset: str, from_ms: int, to_ms: int
    ) -> list[ChainlinkTick]:
        """
        Return all ticks with from_ms <= source_ts_ms <= to_ms, ordered ascending.

        Used for diagnostics and multi-window reconciliation.
        """
        return sorted(
            (
                t for t in self._ticks.get(asset, deque())
                if from_ms <= t.source_ts_ms <= to_ms
            ),
            key=lambda t: t.source_ts_ms,
        )

    def get_candles(
        self,
        asset: str,
        interval_seconds: int = 300,
        limit: int = 80,
    ) -> list[OHLCCandle]:
        """
        Aggregate tick history into OHLC candles from RTDS ticks only.

        Returns a list ordered oldest-first, capped at *limit* candles.
        No Binance data is used.
        """
        ticks = list(self._ticks.get(asset, deque()))
        if not ticks:
            return []

        candle_map: dict[int, OHLCCandle] = {}
        for tick in ticks:
            t_unix = tick.received_at.timestamp()
            bucket = int(t_unix // interval_seconds) * interval_seconds
            if bucket not in candle_map:
                candle_map[bucket] = OHLCCandle(
                    time=bucket,
                    open=tick.value,
                    high=tick.value,
                    low=tick.value,
                    close=tick.value,
                    tick_count=1,
                )
            else:
                c = candle_map[bucket]
                if tick.value > c.high:
                    c.high = tick.value
                if tick.value < c.low:
                    c.low = tick.value
                c.close = tick.value
                c.tick_count += 1

        ordered = sorted(candle_map.values(), key=lambda c: c.time)
        return ordered[-limit:] if len(ordered) > limit else ordered

    # ── State properties ──────────────────────────────────────────────────────

    @property
    def session_start(self) -> datetime:
        return self._session_start

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def subscribed(self) -> bool:
        return self._subscribed

    @property
    def receiving(self) -> bool:
        return self._receiving

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    @property
    def parse_error_count(self) -> int:
        return self._parse_error_count

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_message_at(self) -> Optional[datetime]:
        return self._last_message_at

    @property
    def last_valid_tick_at(self) -> Optional[datetime]:
        return self._last_valid_tick_at

    @property
    def subscription_payload_version(self) -> str:
        return SUBSCRIPTION_PAYLOAD_VERSION

    # ── Background task ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Main reconnect loop.  Runs forever until ``stop()`` is called.
        """
        logger.info(
            "[CHAINLINK] RTDS client starting",
            url=settings.CHAINLINK_WS_URL,
            topic=settings.CHAINLINK_TOPIC,
            subscription_payload_version=SUBSCRIPTION_PAYLOAD_VERSION,
        )
        first = True
        while not self._stop_event.is_set():
            if not first:
                self._reconnect_count += 1
            first = False
            try:
                await self._connect_and_stream()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                self._subscribed = False
                self._last_error = str(exc)
                logger.warning(
                    "[CHAINLINK] Connection lost — will reconnect",
                    error=str(exc),
                    reconnect_in=settings.CHAINLINK_RECONNECT_SECONDS,
                    reconnect_count=self._reconnect_count,
                )
            if not self._stop_event.is_set():
                await asyncio.sleep(settings.CHAINLINK_RECONNECT_SECONDS)
        logger.info("[CHAINLINK] RTDS client stopped")

    async def stop(self) -> None:
        """Signal the reconnect loop to exit."""
        self._stop_event.set()

    async def _ping_loop(self, ws) -> None:
        """
        Send literal string "PING" to the server every 5 seconds.

        One ping task is created per connection; it is cancelled when the
        connection closes.  Does NOT create duplicate tasks on reconnect.
        """
        try:
            while True:
                await asyncio.sleep(5)
                await ws.send("PING")
                logger.debug("[CHAINLINK] PING sent")
        except asyncio.CancelledError:
            logger.debug("[CHAINLINK] PING task cancelled")
        except Exception as exc:
            logger.debug("[CHAINLINK] PING task error", error=str(exc))

    async def _connect_and_stream(self) -> None:
        """Single connection lifecycle: connect → subscribe → receive."""
        async with websockets.connect(
            settings.CHAINLINK_WS_URL,
            ping_interval=None,   # Application-level PING replaces transport ping
            ping_timeout=None,
            close_timeout=10,
            max_size=2**20,  # 1 MB
        ) as ws:
            self._connected = True
            self._subscribed = False
            logger.info("[CHAINLINK] WebSocket connected", url=settings.CHAINLINK_WS_URL)

            # ── Send official subscription payload ────────────────────────────
            sub_json = json.dumps(OFFICIAL_SUBSCRIPTION_PAYLOAD)
            await ws.send(sub_json)
            # subscribed = True immediately after successful send;
            # we do NOT wait for an acknowledgement because the feed
            # may not send one.
            self._subscribed = True
            logger.info(
                "[CHAINLINK] Official subscription sent",
                topic=settings.CHAINLINK_TOPIC,
                version=SUBSCRIPTION_PAYLOAD_VERSION,
            )

            # ── Start application-level PING task (exactly one per connection) ─
            ping_task = asyncio.create_task(self._ping_loop(ws))

            try:
                async for raw_msg in ws:
                    if self._stop_event.is_set():
                        break
                    self._last_message_at = datetime.now(timezone.utc)
                    try:
                        self._handle_message(raw_msg)
                    except Exception as exc:
                        self._parse_error_count += 1
                        self._last_error = f"parse: {exc}"
                        logger.debug(
                            "[CHAINLINK] Message parse error",
                            error=str(exc),
                            raw=str(raw_msg)[:200],
                        )
            finally:
                # Cancel ping task when connection closes — never survives reconnect
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
                self._connected = False
                self._subscribed = False

    # ── Message handling ─────────────────────────────────────────────────────

    def _handle_message(self, raw: str | bytes) -> None:
        """
        Parse one RTDS message and update internal state.

        Official format accepted:
          {
            "topic": "crypto_prices_chainlink",
            "type": "update",
            "payload": {
              "symbol": "btc/usd",
              "timestamp": <ms>,
              "value": <number>,
              "full_accuracy_value": "<string>"
            }
          }

        Rejects:
          - malformed JSON
          - missing required fields
          - non-numeric or non-positive value
          - out-of-order source timestamps
          - unknown symbols (from primary market state)
        """
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        # Server keepalive response — ignore silently
        if isinstance(raw, str) and raw.strip().upper() in ("PONG", "PING"):
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        if not isinstance(msg, dict):
            return

        # Only process official update messages on the correct topic
        msg_topic = (msg.get("topic") or "").lower().strip()
        msg_type = (msg.get("type") or "").lower().strip()

        # Accept only valid updates on the subscribed topic
        if msg_topic != settings.CHAINLINK_TOPIC.lower():
            return
        if msg_type != "update":
            return

        payload = msg.get("payload")
        if not isinstance(payload, dict):
            return

        # ── Parse payload fields ──────────────────────────────────────────────
        symbol = str(payload.get("symbol") or "").lower().strip()
        asset = SYMBOL_TO_ASSET.get(symbol)
        if asset is None:
            # Unknown symbol — discard without corrupting primary state
            return

        raw_value = payload.get("value")
        if raw_value is None:
            return
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return
        if value <= 0:
            return

        full_accuracy_value = str(payload.get("full_accuracy_value") or raw_value)

        # Outer timestamp (message envelope)
        raw_outer_ts = msg.get("timestamp")

        # Source timestamp from payload (ms)
        raw_ts = payload.get("timestamp")
        now = datetime.now(timezone.utc)
        if raw_ts is not None:
            try:
                source_ts_ms = int(raw_ts)
            except (TypeError, ValueError):
                source_ts_ms = int(now.timestamp() * 1000)
        else:
            source_ts_ms = int(now.timestamp() * 1000)

        # Out-of-order guard — discard if older than last accepted tick for symbol
        last_ts = self._last_sequence.get(symbol, 0)
        if source_ts_ms < last_ts:
            logger.debug(
                "[CHAINLINK] Out-of-order tick discarded",
                symbol=symbol,
                source_ts_ms=source_ts_ms,
                last_ts=last_ts,
            )
            return
        self._last_sequence[symbol] = source_ts_ms

        # ── Store tick ────────────────────────────────────────────────────────
        tick = ChainlinkTick(
            symbol=symbol,
            asset=asset,
            value=value,
            full_accuracy_value=full_accuracy_value,
            source_ts_ms=source_ts_ms,
            received_at=now,
        )
        self._ticks[asset].append(tick)
        self._update_counts[asset] = self._update_counts.get(asset, 0) + 1

        self._latest[asset] = ChainlinkPrice(
            asset=asset,
            symbol=symbol,
            value=value,
            full_accuracy_value=full_accuracy_value,
            source=PRICE_SOURCE,
            source_ts_ms=source_ts_ms,
            received_at=now,
            update_count=self._update_counts[asset],
        )

        # Mark receiving=True on first valid tick
        if not self._receiving:
            self._receiving = True
            logger.info("[CHAINLINK] First valid tick received — receiving=True", asset=asset)

        self._last_valid_tick_at = now

        logger.debug(
            "[CHAINLINK] Tick received",
            asset=asset,
            value=value,
            full_accuracy_value=full_accuracy_value,
            source_ts_ms=source_ts_ms,
            age_ms=int(now.timestamp() * 1000) - source_ts_ms,
        )


# ── Singleton management ──────────────────────────────────────────────────────

_singleton: Optional[ChainlinkRTDSClient] = None


def get_chainlink_client() -> Optional[ChainlinkRTDSClient]:
    """Return the global ChainlinkRTDSClient, or None if not yet started."""
    return _singleton


def set_chainlink_client(client: ChainlinkRTDSClient) -> None:
    """Register the global singleton (called from main.py lifespan)."""
    global _singleton
    _singleton = client
