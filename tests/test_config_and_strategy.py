"""Testes de config e estratégia placeholder (sem terminal MT5)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mt5_ea.config import load_settings
from mt5_ea.connection import TickSnapshot
from mt5_ea.strategy import PlaceholderStrategy


def test_load_settings_from_example(monkeypatch) -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"
    assert example.exists()

    for key in list(__import__("os").environ):
        if key.startswith(("MT5_", "STRATEGY_", "RISK_")):
            monkeypatch.delenv(key, raising=False)

    settings = load_settings(example)
    assert settings.symbol == "EURUSD"
    assert settings.dry_run is True
    assert settings.ema_fast == 12
    assert settings.ema_slow == 26
    assert settings.atr_period == 14
    assert settings.risk_mode == "percent"
    assert settings.max_positions == 1
    assert settings.bars >= 60


def test_placeholder_strategy_holds() -> None:
    strat = PlaceholderStrategy()
    tick = TickSnapshot(
        symbol="EURUSD",
        time=datetime.now(),
        bid=1.1,
        ask=1.1001,
        last=1.1,
        volume=10,
    )
    bars = [
        {
            "time": datetime.now(),
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "tick_volume": 1,
        },
        {
            "time": datetime.now(),
            "open": 1.05,
            "high": 1.12,
            "low": 1.04,
            "close": 1.1,
            "tick_volume": 2,
        },
    ]
    signal = strat.evaluate(tick, bars)
    assert signal.action == "hold"
    assert "placeholder" in signal.reason
