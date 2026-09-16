"""Testes de sinal Dual EMA + ATR (sem MT5)."""

from __future__ import annotations

from datetime import datetime, timedelta

from mt5_ea.connection import TickSnapshot
from mt5_ea.strategy import DualEmaAtrParams, DualEmaAtrStrategy, Signal


def _bars_from_closes(closes: list[float], start: datetime | None = None) -> list[dict]:
    t0 = start or datetime(2024, 1, 1, 12, 0, 0)
    bars: list[dict] = []
    for i, close in enumerate(closes):
        bars.append(
            {
                "time": t0 + timedelta(minutes=15 * i),
                "open": close,
                "high": close + 0.0005,
                "low": close - 0.0005,
                "close": close,
                "tick_volume": 100,
            }
        )
    return bars


def _tick(bid: float = 1.1000, ask: float = 1.1002) -> TickSnapshot:
    return TickSnapshot(
        symbol="EURUSD",
        time=datetime(2024, 1, 2, 12, 0, 0),
        bid=bid,
        ask=ask,
        last=bid,
        volume=1,
    )


def _first_signal(
    closes: list[float],
    params: DualEmaAtrParams,
    *,
    open_side: str | None = None,
    want: str,
) -> Signal:
    """Varre a série até o primeiro sinal desejado (cruzamento na barra fechada)."""
    strat = DualEmaAtrStrategy(params)
    for end in range(params.min_bars(), len(closes) + 1):
        # +1 barra "em formação" espelhando o último close
        window = closes[:end] + [closes[end - 1]]
        px = window[-1]
        signal = strat.evaluate(
            _tick(bid=px, ask=px + 0.0002),
            _bars_from_closes(window),
            open_side=open_side,
        )
        if signal.action == want:
            return signal
    raise AssertionError(f"sinal {want!r} não encontrado na série sintética")


def test_insufficient_bars_holds() -> None:
    strat = DualEmaAtrStrategy(DualEmaAtrParams(ema_fast=3, ema_slow=5, atr_period=3))
    signal = strat.evaluate(_tick(), _bars_from_closes([1.0, 1.1, 1.2]))
    assert signal.action == "hold"
    assert "insuficientes" in signal.reason


def test_bullish_cross_enters_long() -> None:
    down = [1.20 - i * 0.002 for i in range(40)]
    up = [down[-1] + i * 0.003 for i in range(1, 30)]
    closes = down + up
    params = DualEmaAtrParams(
        ema_fast=5, ema_slow=12, atr_period=5, atr_sl_mult=1.5, atr_tp_mult=2.0
    )
    signal = _first_signal(closes, params, want="enter_long")
    assert signal.stop_loss is not None and signal.take_profit is not None
    assert signal.entry_price is not None
    assert signal.stop_loss < signal.entry_price < signal.take_profit
    assert signal.atr is not None and signal.atr > 0


def test_bearish_cross_enters_short() -> None:
    up = [1.00 + i * 0.002 for i in range(40)]
    down = [up[-1] - i * 0.003 for i in range(1, 30)]
    closes = up + down
    params = DualEmaAtrParams(ema_fast=5, ema_slow=12, atr_period=5)
    signal = _first_signal(closes, params, want="enter_short")
    assert signal.stop_loss is not None and signal.take_profit is not None
    assert signal.entry_price is not None
    assert signal.take_profit < signal.entry_price < signal.stop_loss


def test_exit_long_on_bearish_cross() -> None:
    up = [1.00 + i * 0.002 for i in range(40)]
    down = [up[-1] - i * 0.003 for i in range(1, 30)]
    closes = up + down
    params = DualEmaAtrParams(ema_fast=5, ema_slow=12, atr_period=5)
    signal = _first_signal(closes, params, open_side="buy", want="exit_long")
    assert "saída long" in signal.reason


def test_holds_without_cross_when_flat() -> None:
    closes = [1.0 + i * 0.0001 for i in range(80)]
    strat = DualEmaAtrStrategy(DualEmaAtrParams(ema_fast=5, ema_slow=20, atr_period=5))
    # inclui barra em formação
    bars = _bars_from_closes(closes + [closes[-1]])
    signal = strat.evaluate(_tick(), bars, open_side=None)
    assert signal.action == "hold"
    assert signal.ema_fast is not None
