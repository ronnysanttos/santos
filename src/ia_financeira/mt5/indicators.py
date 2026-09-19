"""Indicadores técnicos puros (sem dependência do terminal MT5)."""

from __future__ import annotations

from typing import Sequence


def sma(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period deve ser >= 1")
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    window = sum(values[:period])
    out[period - 1] = window / period
    for i in range(period, n):
        window += values[i] - values[i - period]
        out[i] = window / period
    return out


def rsi(closes: Sequence[float], period: int = 14) -> list[float | None]:
    """RSI de Wilder."""
    if period < 1:
        raise ValueError("period deve ser >= 1")
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_from_avgs(avg_gain, avg_loss)

    for i in range(period + 1, n):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_from_avgs(avg_gain, avg_loss)
    return out


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    """ATR de Wilder."""
    if period < 1:
        raise ValueError("period deve ser >= 1")
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows e closes devem ter o mesmo tamanho")

    out: list[float | None] = [None] * n
    if n < period + 1:
        return out

    trs: list[float] = []
    for i in range(1, n):
        trs.append(true_range(highs[i], lows[i], closes[i - 1]))

    first_atr = sum(trs[:period]) / period
    out[period] = first_atr
    prev = first_atr
    for i in range(period, len(trs)):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i + 1] = prev
    return out


def last_valid(series: Sequence[float | None]) -> float | None:
    for value in reversed(series):
        if value is not None:
            return float(value)
    return None
