"""Testes leves que não dependem do terminal MetaTrader 5."""

from __future__ import annotations

from pathlib import Path

from mt5_ea.config import load_settings
from mt5_ea.strategy import PlaceholderStrategy
from mt5_ea.connection import TickSnapshot
from datetime import datetime


def test_load_settings_from_example(tmp_path: Path, monkeypatch) -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"
    assert example.exists()

    # Isola env do host
    for key in list(__import__("os").environ):
        if key.startswith("MT5_"):
            monkeypatch.delenv(key, raising=False)

    settings = load_settings(example)
    assert settings.symbol == "EURUSD"
    assert settings.dry_run is True
    assert settings.timeframe_minutes == 5
    assert settings.bars == 20


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
    signal = strat.on_tick(tick, bars)
    assert signal.action == "hold"
    assert "placeholder" in signal.reason
