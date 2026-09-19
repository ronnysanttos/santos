from __future__ import annotations

from ia_financeira.mt5.indicators import atr, last_valid, rsi, sma


def test_sma_and_rsi_atr_on_synthetic_series():
    closes = [float(i) for i in range(1, 31)]  # trending up
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]

    ma = sma(closes, 5)
    assert last_valid(ma) is not None
    assert ma[4] == sum(closes[:5]) / 5

    r = rsi(closes, 14)
    assert last_valid(r) is not None
    # série monotônica de alta → RSI alto
    assert last_valid(r) > 70

    a = atr(highs, lows, closes, 14)
    assert last_valid(a) is not None
    assert last_valid(a) > 0
