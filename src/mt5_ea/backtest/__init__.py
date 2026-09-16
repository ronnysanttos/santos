"""Pacote de backtest offline para a estratégia Dual EMA + ATR."""

from mt5_ea.backtest.engine import BacktestConfig, BacktestEngine
from mt5_ea.backtest.metrics import BacktestMetrics

__all__ = ["BacktestConfig", "BacktestEngine", "BacktestMetrics"]
