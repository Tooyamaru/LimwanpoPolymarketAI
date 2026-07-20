"""
Chainlink RTDS Client — Polymarket Real-Time Data Service.

Connects to wss://ws-live-data.polymarket.com and subscribes to the
crypto_prices_chainlink topic for live Chainlink oracle prices.

Supported symbols: btc/usd, eth/usd, sol/usd, xrp/usd
Asset labels:      BTC,     ETH,     SOL,     XRP

Price source label: POLYMARKET_RTDS_CHAINLINK

Architecture:
  - Singleton client; started as an asyncio task in main.py lifespan.
  - Maintains latest price per asset in memory (dict).
  - Maintains a per-asset tick deque (size: CHAINLINK_TICK_HISTORY_SIZE)
    for OHLC candle aggregation.
  - Health = connected AND subscribed AND all assets have a message within
    CHAINLINK_STALE_SECONDS.
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

# Chainlink symbol → canonical asset name
SYMBOL_TO_ASSET: dict[str, str] = {
    "btc/usd": "BTC",
    "eth/usd": "ETH",
    "sol/usd": "SOL",
    "xrp/usd": "XRP",
}
ASSET_TO_SYMBOL: dict[str, str] = {v: k for k, v in SYMBOL_TO_ASSET.items()}


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class ChainlinkTick:
    """A single price observation received from the RTDS feed."""

    symbol: str           # e.g. "btc/usd"
    asset: str            # e.g. "BTC"
    value: float          # Chainlink oracle price
    source_ts_ms: int     # ms timestamp from the RTDS message
    received_at: datetime # when this process received the tick


@dataclass
class ChainlinkPrice:
    """Snapshot of the latest known price for one asset."""

    asset: str
    symbol: str
    value: float
    source: str                   # always POLYMARKET_RTDS_CHAINLINK
    source_ts_ms: int             # ms timestamp from the RTDS message
    received_at: datetime
    age_ms: float = 0.0
    stale: bool = False
    connected: bool = False
    subscribed: bool = False
    healthy: bool = False
    update_count: int = 0

    @property
    def source_ts_iso(self) -> str:
        return datetime.fromtimestamp(self.source_ts_ms / 1000, tz=timezone.utc).isoformat()


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
    """

    def __init__(self) -> None:
        self._latest: dict[str, ChainlinkPrice] = {}
        self._ticks: dict[str, deque[ChainlinkTick]] = {
            asset: deque(maxlen=settings.CHAINLINK_TICK_HISTORY_SIZE)
            for asset in SYMBOL_TO_ASSET.values()
        }
        self._session_start: datetime = datetime.now(timezone.utc)
        self._connected: bool = False
        self._subscribed: bool = False
        self._update_counts: dict[str, int] = {
            asset: 0 for asset in SYMBOL_TO_ASSET.values()
        }
        self._last_sequence: dict[str, int] = {}  # per-symbol latest source_ts_ms
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
            source=base.source,
            source_ts_ms=base.source_ts_ms,
            received_at=base.received_at,
            age_ms=round(age_ms),
            stale=stale,
            connected=self._connected,
            subscribed=self._subscribed,
            healthy=self._connected and self._subscribed and not stale,
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
        """True when connected, subscribed, and every asset has a fresh tick."""
        if not (self._connected and self._subscribed):
            return False
        threshold_ms = settings.CHAINLINK_STALE_SECONDS * 1000
        now_ms = time.time() * 1000
        for asset in SYMBOL_TO_ASSET.values():
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

    def get_candles(
        self,
        asset: str,
        interval_seconds: int = 300,
        limit: int = 80,
    ) -> list[OHLCCandle]:
        """
        Aggregate tick history into OHLC candles.

        Returns a list ordered oldest-first, capped at *limit* candles.
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

    @property
    def session_start(self) -> datetime:
        return self._session_start

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def subscribed(self) -> bool:
        return self._subscribed

    # ── Background task ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Main reconnect loop.  Runs forever until ``stop()`` is called.
        """
        logger.info(
            "[CHAINLINK] RTDS client starting",
            url=settings.CHAINLINK_WS_URL,
            topic=settings.CHAINLINK_TOPIC,
        )
        while not self._stop_event.is_set():
            try:
                await self._connect_and_stream()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._connected = False
                self._subscribed = False
                logger.warning(
                    "[CHAINLINK] Connection lost — will reconnect",
                    error=str(exc),
                    reconnect_in=settings.CHAINLINK_RECONNECT_SECONDS,
                )
            if not self._stop_event.is_set():
                await asyncio.sleep(settings.CHAINLINK_RECONNECT_SECONDS)
        logger.info("[CHAINLINK] RTDS client stopped")

    async def stop(self) -> None:
        """Signal the reconnect loop to exit."""
        self._stop_event.set()

    async def _connect_and_stream(self) -> None:
        """Single connection lifecycle: connect → subscribe → receive."""
        async with websockets.connect(
            settings.CHAINLINK_WS_URL,
            ping_interval=30,
            ping_timeout=20,
            close_timeout=10,
            max_size=2**20,  # 1 MB
        ) as ws:
            self._connected = True
            logger.info("[CHAINLINK] WebSocket connected", url=settings.CHAINLINK_WS_URL)

            # Send subscription
            sub = json.dumps(
                {"type": "subscribe", "topic": settings.CHAINLINK_TOPIC}
            )
            await ws.send(sub)
            logger.info("[CHAINLINK] Subscription sent", topic=settings.CHAINLINK_TOPIC)

            async for raw_msg in ws:
                if self._stop_event.is_set():
                    break
                try:
                    self._handle_message(raw_msg)
                except Exception as exc:
                    logger.debug(
                        "[CHAINLINK] Message parse error",
                        error=str(exc),
                        raw=str(raw_msg)[:200],
                    )

    # ── Message handling ─────────────────────────────────────────────────────

    def _handle_message(self, raw: str | bytes) -> None:
        """Parse one RTDS message and update internal state."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = (msg.get("type") or msg.get("event") or "").lower()

        # ── Subscription confirmation ──────────────────────────────────────
        if msg_type in ("subscribed", "confirm", "ack", "subscription") or (
            msg.get("status") in ("subscribed", "ok", "success")
        ):
            self._subscribed = True
            logger.info(
                "[CHAINLINK] Subscription confirmed",
                topic=settings.CHAINLINK_TOPIC,
            )
            return

        # ── Price data ────────────────────────────────────────────────────
        topic = (msg.get("topic") or "").lower()
        if topic and topic != settings.CHAINLINK_TOPIC.lower():
            return  # different topic; ignore

        now = datetime.now(timezone.utc)

        # Support two common RTDS message formats:
        # Format A — flat:   {"type":"data","symbol":"btc/usd","value":"64806","timestamp":...}
        # Format B — nested: {"type":"data","data":[{"symbol":"btc/usd","value":"64806",...}]}
        items: list[dict] = []
        if "symbol" in msg and ("value" in msg or "price" in msg):
            items = [msg]
        elif isinstance(msg.get("data"), list):
            items = [i for i in msg["data"] if isinstance(i, dict)]
        elif isinstance(msg.get("data"), dict):
            items = [msg["data"]]

        for item in items:
            symbol = str(
                item.get("symbol") or item.get("sym") or ""
            ).lower().strip()
            asset = SYMBOL_TO_ASSET.get(symbol)
            if asset is None:
                continue

            raw_value = item.get("value") or item.get("price") or item.get("v")
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue

            # Source timestamp (ms)
            raw_ts = item.get("timestamp") or item.get("ts") or item.get("t")
            if raw_ts is not None:
                try:
                    source_ts_ms = int(raw_ts)
                except (TypeError, ValueError):
                    source_ts_ms = int(now.timestamp() * 1000)
            else:
                source_ts_ms = int(now.timestamp() * 1000)

            # Out-of-order guard
            last_ts = self._last_sequence.get(symbol, 0)
            if source_ts_ms < last_ts:
                logger.debug(
                    "[CHAINLINK] Out-of-order tick discarded",
                    symbol=symbol,
                    source_ts_ms=source_ts_ms,
                    last_ts=last_ts,
                )
                continue
            self._last_sequence[symbol] = source_ts_ms
            self._subscribed = True  # receiving data confirms subscription

            tick = ChainlinkTick(
                symbol=symbol,
                asset=asset,
                value=value,
                source_ts_ms=source_ts_ms,
                received_at=now,
            )
            self._ticks[asset].append(tick)
            self._update_counts[asset] = self._update_counts.get(asset, 0) + 1

            self._latest[asset] = ChainlinkPrice(
                asset=asset,
                symbol=symbol,
                value=value,
                source=PRICE_SOURCE,
                source_ts_ms=source_ts_ms,
                received_at=now,
                update_count=self._update_counts[asset],
            )

            logger.debug(
                "[CHAINLINK] Tick received",
                asset=asset,
                value=value,
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
