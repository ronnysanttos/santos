"""Testes unitários de EMA / ATR (sem MT5)."""

from __future__ import annotations

from mt5_ea.indicators import atr, ema, true_range


def test_ema_constant_series() -> None:
    values = [10.0] * 20
    series = ema(values, 5)
    assert series[4] == 10.0
    assert series[-1] == 10.0
    assert series[0] is None


def test_ema_rises_with_uptrend() -> None:
    values = [float(i) for i in range(1, 31)]
    series = ema(values, 10)
    assert series[9] is not None
    assert series[-1] is not None
    assert series[-1] > series[9]  # type: ignore[operator]


def test_true_range() -> None:
    assert true_range(12, 10, 11) == 2
    assert true_range(12, 10, 9) == 3  # |12-9|
    assert true_range(12, 10, 13) == 3  # |10-13|


def test_atr_warmup_and_positive() -> None:
    n = 40
    highs = [1.10 + (i % 5) * 0.001 for i in range(n)]
    lows = [h - 0.002 for h in highs]
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    series = atr(highs, lows, closes, 14)
    assert all(v is None for v in series[:14])
    assert series[14] is not None
    assert series[-1] is not None
    assert series[-1] > 0  # type: ignore[operator]
