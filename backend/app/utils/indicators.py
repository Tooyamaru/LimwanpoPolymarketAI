"""
utils/indicators.py — Shared pure-function technical indicators.

Used by the Decision Engine pipeline (Momentum / Trend / Volatility engines).
Every function is a stateless, pure calculation over a list of floats — no
DB access, no I/O, no side effects. This keeps the indicator math testable
in isolation and reusable across engines.

All functions return ``None`` (or a tuple of ``None``s) when there is not
enough history to compute a stable value, so callers can treat "insufficient
data" as an explicit, checkable case rather than a crash or a misleading 0.
"""

from typing import Optional


def ema_series(values: list[float], period: int) -> list[float]:
    """Return the full EMA series for *values* using the given *period*."""
    if not values or period <= 0:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def ema_last(values: list[float], period: int) -> Optional[float]:
    """Return only the most recent EMA value, or None if no data."""
    if len(values) < period:
        return None
    series = ema_series(values, period)
    return series[-1] if series else None


def rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """
    Relative Strength Index (Wilder-style, simple moving average variant).

    Returns a value in [0, 100], or None if there isn't enough history
    (need at least period + 1 closes).
    """
    if len(closes) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    MACD line, signal line, and histogram.

    Returns (macd_line, signal_line, histogram) or (None, None, None) if
    there isn't enough history (need at least slow + signal closes).
    """
    if len(closes) < slow + signal:
        return None, None, None

    ema_fast_series = ema_series(closes, fast)
    ema_slow_series = ema_series(closes, slow)
    n = min(len(ema_fast_series), len(ema_slow_series))
    macd_line_series = [
        ema_fast_series[-n + i] - ema_slow_series[-n + i] for i in range(n)
    ]
    signal_series = ema_series(macd_line_series, signal)

    macd_val = macd_line_series[-1]
    signal_val = signal_series[-1]
    hist = macd_val - signal_val
    return round(macd_val, 6), round(signal_val, 6), round(hist, 6)


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> Optional[float]:
    """
    Average True Range — a volatility measure in the same unit as price.

    Returns None if there isn't enough history (need at least period + 1
    candles).
    """
    if len(closes) < period + 1 or len(highs) != len(closes) or len(lows) != len(closes):
        return None

    true_ranges: list[float] = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    return round(sum(true_ranges[-period:]) / period, 6)


def roc(closes: list[float], period: int = 10) -> Optional[float]:
    """
    Rate of Change over *period* candles, expressed as a percentage.

    Returns None if there aren't enough closes (need period + 1).
    """
    if len(closes) < period + 1:
        return None
    prev = closes[-period - 1]
    curr = closes[-1]
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100.0, 4)


def vwap(closes: list[float], volumes: list[float]) -> Optional[float]:
    """
    Volume-weighted average price over the given window.

    Returns None if inputs are empty, mismatched, or total volume is 0.
    """
    if not closes or not volumes or len(closes) != len(volumes):
        return None
    total_vol = sum(volumes)
    if total_vol == 0:
        return None
    return round(sum(c * v for c, v in zip(closes, volumes)) / total_vol, 6)
