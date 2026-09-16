"""Testes do backtest offline (sem terminal MT5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from mt5_ea.backtest.data import Bar, generate_synthetic_ohlc, load_csv
from mt5_ea.backtest.engine import BacktestConfig, BacktestEngine
from mt5_ea.backtest.metrics import EquityPoint, TradeResult, compute_metrics
from mt5_ea.risk import RiskParams
from mt5_ea.strategy import DualEmaAtrParams


FIXTURE = Path(__file__).parent / "fixtures" / "ohlc_eurusd_m15.csv"


def test_load_fixture_csv() -> None:
    bars = load_csv(FIXTURE)
    assert len(bars) == 240
    assert bars[0].high >= bars[0].low


def test_metrics_math() -> None:
    t0 = datetime(2024, 1, 1)
    trades = [
        TradeResult(
            side="buy",
            volume=0.1,
            entry_time=t0,
            exit_time=t0 + timedelta(hours=1),
            entry_price=1.1,
            exit_price=1.2,
            stop_loss=1.0,
            take_profit=1.3,
            pnl=100.0,
            reason_entry="e",
            reason_exit="tp",
        ),
        TradeResult(
            side="sell",
            volume=0.1,
            entry_time=t0,
            exit_time=t0 + timedelta(hours=2),
            entry_price=1.2,
            exit_price=1.25,
            stop_loss=1.3,
            take_profit=1.1,
            pnl=-50.0,
            reason_entry="e",
            reason_exit="sl",
        ),
    ]
    curve = [
        EquityPoint(t0, 10_000),
        EquityPoint(t0 + timedelta(hours=1), 10_100),
        EquityPoint(t0 + timedelta(hours=2), 10_050),
    ]
    m = compute_metrics(initial_equity=10_000, trades=trades, equity_curve=curve)
    assert m.net_profit == 50.0
    assert m.trades == 2
    assert m.wins == 1 and m.losses == 1
    assert abs(m.win_rate - 50.0) < 1e-9
    assert abs(m.profit_factor - 2.0) < 1e-9
    assert m.max_drawdown == 50.0


def test_synthetic_backtest_produces_trades() -> None:
    bars = generate_synthetic_ohlc(bars=300, seed=42, timeframe_minutes=15)
    engine = BacktestEngine(
        BacktestConfig(
            initial_equity=10_000,
            spread_points=10,
            strategy_params=DualEmaAtrParams(
                ema_fast=5, ema_slow=15, atr_period=7, atr_sl_mult=1.2, atr_tp_mult=2.0
            ),
            risk_params=RiskParams(
                mode="fixed",
                fixed_lots=0.10,
                max_daily_loss_percent=0.0,
                max_spread_points=0.0,
                session_start_hour=None,
                session_end_hour=None,
            ),
        )
    )
    metrics = engine.run(bars)
    assert metrics.trades >= 1
    assert len(metrics.equity_curve) >= 2
    assert metrics.final_equity == metrics.initial_equity + metrics.net_profit


def test_fixture_csv_backtest_known_behavior() -> None:
    bars = load_csv(FIXTURE)
    engine = BacktestEngine(
        BacktestConfig(
            initial_equity=10_000,
            spread_points=10,
            strategy_params=DualEmaAtrParams(
                ema_fast=8, ema_slow=21, atr_period=10, atr_sl_mult=1.5, atr_tp_mult=2.5
            ),
            risk_params=RiskParams(
                mode="fixed",
                fixed_lots=0.10,
                max_daily_loss_percent=0.0,
                max_spread_points=0.0,
                session_start_hour=None,
                session_end_hour=None,
            ),
        )
    )
    metrics = engine.run(bars)
    # Série down→up→down deve gerar pelo menos um cruzamento negociável
    assert metrics.trades >= 1
    # Drawdown e equity curve coerentes
    assert metrics.max_drawdown >= 0
    assert metrics.max_drawdown_pct >= 0
    assert metrics.equity_curve[-1].equity == metrics.final_equity


def test_forced_cross_enters_and_stops() -> None:
    """Constrói OHLC onde um long entra e bate TP de forma determinística."""
    # Tendência de baixa longa + alta forte (cross up), depois spike de alta (TP)
    t0 = datetime(2024, 3, 1, 10, 0, 0)
    closes: list[float] = []
    px = 1.2000
    for i in range(60):
        px -= 0.0010
        closes.append(px)
    for i in range(40):
        px += 0.0020
        closes.append(px)
    # barra extra alta para garantir TP depois da entrada
    for i in range(15):
        px += 0.0030
        closes.append(px)

    bars: list[Bar] = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        h = max(o, c) + 0.0003
        low = min(o, c) - 0.0003
        bars.append(
            Bar(
                time=t0 + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=low,
                close=c,
                volume=100,
            )
        )
        prev = c

    engine = BacktestEngine(
        BacktestConfig(
            initial_equity=10_000,
            spread_points=0,
            strategy_params=DualEmaAtrParams(
                ema_fast=5, ema_slow=12, atr_period=5, atr_sl_mult=1.0, atr_tp_mult=1.5
            ),
            risk_params=RiskParams(
                mode="fixed",
                fixed_lots=0.10,
                max_daily_loss_percent=0.0,
                max_spread_points=0.0,
                session_start_hour=None,
                session_end_hour=None,
            ),
        )
    )
    metrics = engine.run(bars)
    assert metrics.trades >= 1
    assert any(t.side == "buy" for t in metrics.trade_list)
