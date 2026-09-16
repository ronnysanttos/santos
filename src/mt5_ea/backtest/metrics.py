"""Métricas de desempenho do backtest."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TradeResult:
    side: str  # buy | sell
    volume: float
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    pnl: float
    reason_entry: str
    reason_exit: str


@dataclass(frozen=True, slots=True)
class EquityPoint:
    time: datetime
    equity: float


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    initial_equity: float
    final_equity: float
    net_profit: float
    return_pct: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_win: float
    avg_loss: float
    gross_profit: float
    gross_loss: float
    equity_curve: tuple[EquityPoint, ...]
    trade_list: tuple[TradeResult, ...]

    def summary_lines(self) -> list[str]:
        pf = (
            "inf"
            if self.profit_factor == float("inf")
            else f"{self.profit_factor:.2f}"
        )
        return [
            f"Equity inicial : {self.initial_equity:,.2f}",
            f"Equity final   : {self.final_equity:,.2f}",
            f"Lucro líquido  : {self.net_profit:,.2f} ({self.return_pct:+.2f}%)",
            f"Trades         : {self.trades} (wins={self.wins}, losses={self.losses})",
            f"Win rate       : {self.win_rate:.1f}%",
            f"Profit factor  : {pf}",
            f"Max drawdown   : {self.max_drawdown:,.2f} ({self.max_drawdown_pct:.2f}%)",
            f"Avg win / loss : {self.avg_win:,.2f} / {self.avg_loss:,.2f}",
        ]


def compute_metrics(
    *,
    initial_equity: float,
    trades: Sequence[TradeResult],
    equity_curve: Sequence[EquityPoint],
) -> BacktestMetrics:
    if not equity_curve:
        equity_curve = (EquityPoint(time=datetime(1970, 1, 1), equity=initial_equity),)

    final_equity = float(equity_curve[-1].equity)
    net = final_equity - initial_equity
    ret = (net / initial_equity * 100.0) if initial_equity else 0.0

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    else:
        pf = float("inf") if gross_profit > 0 else 0.0

    n = len(trades)
    win_rate = (len(wins) / n * 100.0) if n else 0.0
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0

    max_dd, max_dd_pct = _max_drawdown(equity_curve)

    return BacktestMetrics(
        initial_equity=initial_equity,
        final_equity=final_equity,
        net_profit=net,
        return_pct=ret,
        trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        profit_factor=pf,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        avg_win=avg_win,
        avg_loss=avg_loss,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        equity_curve=tuple(equity_curve),
        trade_list=tuple(trades),
    )


def _max_drawdown(curve: Sequence[EquityPoint]) -> tuple[float, float]:
    peak = curve[0].equity
    max_dd = 0.0
    max_dd_pct = 0.0
    for point in curve:
        if point.equity > peak:
            peak = point.equity
        dd = peak - point.equity
        dd_pct = (dd / peak * 100.0) if peak else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
    return max_dd, max_dd_pct
