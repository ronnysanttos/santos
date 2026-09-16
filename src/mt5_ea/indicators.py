"""Indicadores técnicos puros (sem dependência do terminal MT5)."""

from __future__ import annotations

from typing import Sequence


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """
    EMA clássica.

    Retorna lista do mesmo tamanho de `values`; os primeiros `period-1`
    elementos são None até a semente (SMA) estar disponível.
    """
    if period < 1:
        raise ValueError("period deve ser >= 1")
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out

    seed = sum(values[:period]) / period
    out[period - 1] = seed
    mult = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = (values[i] - prev) * mult + prev
        out[i] = prev
    return out


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    """
    ATR de Wilder (suavização recursiva após a média inicial dos TRs).

    Índice i usa high/low[i] e close[i-1]; o primeiro ATR válido fica em
    `period` (precisa de `period` TRs → `period+1` barras).
    """
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

    # trs[0] corresponde à barra índice 1
    first_atr = sum(trs[:period]) / period
    out[period] = first_atr  # barra índice = period
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


def value_at(series: Sequence[float | None], index: int) -> float | None:
    if index < 0 or index >= len(series):
        return None
    value = series[index]
    return None if value is None else float(value)
