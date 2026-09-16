"""Motor de backtest offline (OHLC) alinhado à estratégia + risco do EA ao vivo."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from mt5_ea.backtest.data import Bar, bars_to_dicts, default_fx_contract
from mt5_ea.backtest.metrics import (
    BacktestMetrics,
    EquityPoint,
    TradeResult,
    compute_metrics,
)
from mt5_ea.connection import TickSnapshot
from mt5_ea.risk import (
    ContractSpec,
    RiskContext,
    RiskManager,
    RiskParams,
    money_at_risk_per_lot,
)
from mt5_ea.strategy import DualEmaAtrParams, DualEmaAtrStrategy, Strategy

logger = logging.getLogger(__name__)


@dataclass
class _OpenPosition:
    side: str
    volume: float
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    reason_entry: str


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    spread_points: float = 10.0
    contract: ContractSpec | None = None
    strategy_params: DualEmaAtrParams | None = None
    risk_params: RiskParams | None = None
    # Se True, avalia SL/TP dentro da barra (high/low); SL tem prioridade se ambos.
    intrabar_stops: bool = True


class BacktestEngine:
    """
    Replay barra a barra:

    1. No fechamento da barra i, monta janela com barra "em formação" sintética
       (igual ao feed live) e avalia DualEmaAtrStrategy + RiskManager.
    2. Entradas executam no **open da barra seguinte** (i+1), com spread.
    3. SL/TP são checados nas barras seguintes via high/low.
    4. Saídas por sinal contrario também no open da barra seguinte.
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        *,
        strategy: Strategy | None = None,
        risk: RiskManager | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        params = self.config.strategy_params or DualEmaAtrParams()
        self.strategy: Strategy = strategy or DualEmaAtrStrategy(params)
        risk_params = self.config.risk_params or RiskParams(
            mode="fixed",
            fixed_lots=0.10,
            max_positions=1,
            max_daily_loss_percent=0.0,
            max_spread_points=0.0,
            session_start_hour=None,
            session_end_hour=None,
        )
        self.risk = risk or RiskManager(risk_params)
        fx = default_fx_contract()
        self.contract = self.config.contract or ContractSpec(
            point=fx["point"],
            digits=int(fx["digits"]),
            volume_min=fx["volume_min"],
            volume_max=fx["volume_max"],
            volume_step=fx["volume_step"],
            tick_size=fx["tick_size"],
            tick_value=fx["tick_value"],
        )
        self.spread_points = (
            self.config.spread_points
            if self.config.spread_points is not None
            else fx["spread_points"]
        )

    def run(self, bars: Sequence[Bar]) -> BacktestMetrics:
        if len(bars) < 3:
            raise ValueError("backtest requer pelo menos 3 barras")

        equity = float(self.config.initial_equity)
        balance = equity
        daily_pnl = 0.0
        current_day: datetime.date | None = None
        position: _OpenPosition | None = None
        pending_decision = None  # executa no open da próxima barra

        trades: list[TradeResult] = []
        curve: list[EquityPoint] = [
            EquityPoint(time=bars[0].time, equity=equity),
        ]

        dict_bars = bars_to_dicts(list(bars))
        min_need = 3
        if hasattr(self.strategy, "params"):
            min_need = max(min_need, self.strategy.params.min_bars())  # type: ignore[attr-defined]

        for i in range(len(bars)):
            bar = bars[i]

            # reset PnL diário
            if current_day is None or bar.time.date() != current_day:
                current_day = bar.time.date()
                daily_pnl = 0.0

            # 1) Executa decisão pendente no open desta barra
            if pending_decision is not None:
                equity, balance, daily_pnl, position, closed = self._execute_pending(
                    decision=pending_decision,
                    bar=bar,
                    equity=equity,
                    balance=balance,
                    daily_pnl=daily_pnl,
                    position=position,
                    trades=trades,
                )
                pending_decision = None
                if closed:
                    curve.append(EquityPoint(time=bar.time, equity=equity))

            # 2) Checa SL/TP intrabar se houver posição
            if position is not None and self.config.intrabar_stops:
                hit = self._check_stops(position, bar)
                if hit is not None:
                    exit_price, reason = hit
                    pnl = self._pnl(position, exit_price)
                    trades.append(
                        TradeResult(
                            side=position.side,
                            volume=position.volume,
                            entry_time=position.entry_time,
                            exit_time=bar.time,
                            entry_price=position.entry_price,
                            exit_price=exit_price,
                            stop_loss=position.stop_loss,
                            take_profit=position.take_profit,
                            pnl=pnl,
                            reason_entry=position.reason_entry,
                            reason_exit=reason,
                        )
                    )
                    equity += pnl
                    balance = equity
                    daily_pnl += pnl
                    logger.debug(
                        "BT stop %s pnl=%.2f equity=%.2f | %s",
                        position.side,
                        pnl,
                        equity,
                        reason,
                    )
                    position = None
                    curve.append(EquityPoint(time=bar.time, equity=equity))

            # 3) Gera sinal no fechamento (com barra em formação dummy)
            if i + 1 < min_need:
                curve.append(EquityPoint(time=bar.time, equity=equity))
                continue

            closed_window = dict_bars[: i + 1]
            forming = {
                "time": bar.time,
                "open": bar.close,
                "high": bar.close,
                "low": bar.close,
                "close": bar.close,
                "tick_volume": 0,
            }
            window = closed_window + [forming]
            half_spread = (self.spread_points * self.contract.point) / 2.0
            mid = bar.close
            tick = TickSnapshot(
                symbol="BACKTEST",
                time=bar.time,
                bid=mid - half_spread,
                ask=mid + half_spread,
                last=mid,
                volume=int(bar.volume),
            )
            open_side = position.side if position else None
            signal = self.strategy.evaluate(tick, window, open_side=open_side)

            ctx = RiskContext(
                equity=equity,
                balance=balance,
                bid=tick.bid,
                ask=tick.ask,
                open_positions=1 if position else 0,
                open_side=open_side,
                daily_pnl=daily_pnl,
                now=bar.time,
                contract=self.contract,
            )
            decision = self.risk.decide(signal, ctx)

            if decision.action != "skip":
                # agenda para o open da próxima barra
                if i + 1 < len(bars):
                    pending_decision = decision
                    logger.debug(
                        "BT sinal@%s → %s (pendente open)",
                        bar.time,
                        decision.action,
                    )
                else:
                    # última barra: fecha a mercado no close se for saída
                    if decision.action in {"exit_long", "exit_short"} and position:
                        exit_price = bar.close
                        pnl = self._pnl(position, exit_price)
                        trades.append(
                            TradeResult(
                                side=position.side,
                                volume=position.volume,
                                entry_time=position.entry_time,
                                exit_time=bar.time,
                                entry_price=position.entry_price,
                                exit_price=exit_price,
                                stop_loss=position.stop_loss,
                                take_profit=position.take_profit,
                                pnl=pnl,
                                reason_entry=position.reason_entry,
                                reason_exit=f"fim dos dados | {decision.reason}",
                            )
                        )
                        equity += pnl
                        balance = equity
                        position = None

            curve.append(EquityPoint(time=bar.time, equity=equity))

        # Fecha posição residual no último close
        if position is not None:
            last = bars[-1]
            pnl = self._pnl(position, last.close)
            trades.append(
                TradeResult(
                    side=position.side,
                    volume=position.volume,
                    entry_time=position.entry_time,
                    exit_time=last.time,
                    entry_price=position.entry_price,
                    exit_price=last.close,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    pnl=pnl,
                    reason_entry=position.reason_entry,
                    reason_exit="fechamento forçado no fim do backtest",
                )
            )
            equity += pnl
            curve.append(EquityPoint(time=last.time, equity=equity))

        return compute_metrics(
            initial_equity=self.config.initial_equity,
            trades=trades,
            equity_curve=curve,
        )

    def _execute_pending(
        self,
        *,
        decision,
        bar: Bar,
        equity: float,
        balance: float,
        daily_pnl: float,
        position: _OpenPosition | None,
        trades: list[TradeResult],
    ) -> tuple[float, float, float, _OpenPosition | None, bool]:
        half_spread = (self.spread_points * self.contract.point) / 2.0
        closed = False

        if decision.action == "enter_long" and position is None:
            entry = bar.open + half_spread
            # reancora SL/TP pela distância do sinal
            sl, tp = self._rebase_stops(
                side="buy",
                entry=entry,
                signal_entry=decision.entry_price,
                signal_sl=decision.stop_loss,
                signal_tp=decision.take_profit,
            )
            position = _OpenPosition(
                side="buy",
                volume=float(decision.volume or 0.0),
                entry_time=bar.time,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                reason_entry=decision.reason,
            )
            logger.debug("BT ENTER long @ %.5f vol=%.2f", entry, position.volume)

        elif decision.action == "enter_short" and position is None:
            entry = bar.open - half_spread
            sl, tp = self._rebase_stops(
                side="sell",
                entry=entry,
                signal_entry=decision.entry_price,
                signal_sl=decision.stop_loss,
                signal_tp=decision.take_profit,
            )
            position = _OpenPosition(
                side="sell",
                volume=float(decision.volume or 0.0),
                entry_time=bar.time,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                reason_entry=decision.reason,
            )
            logger.debug("BT ENTER short @ %.5f vol=%.2f", entry, position.volume)

        elif decision.action == "exit_long" and position and position.side == "buy":
            exit_price = bar.open - half_spread
            pnl = self._pnl(position, exit_price)
            trades.append(
                TradeResult(
                    side=position.side,
                    volume=position.volume,
                    entry_time=position.entry_time,
                    exit_time=bar.time,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    pnl=pnl,
                    reason_entry=position.reason_entry,
                    reason_exit=decision.reason,
                )
            )
            equity += pnl
            balance = equity
            daily_pnl += pnl
            position = None
            closed = True

        elif decision.action == "exit_short" and position and position.side == "sell":
            exit_price = bar.open + half_spread
            pnl = self._pnl(position, exit_price)
            trades.append(
                TradeResult(
                    side=position.side,
                    volume=position.volume,
                    entry_time=position.entry_time,
                    exit_time=bar.time,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    pnl=pnl,
                    reason_entry=position.reason_entry,
                    reason_exit=decision.reason,
                )
            )
            equity += pnl
            balance = equity
            daily_pnl += pnl
            position = None
            closed = True

        return equity, balance, daily_pnl, position, closed

    @staticmethod
    def _rebase_stops(
        *,
        side: str,
        entry: float,
        signal_entry: float | None,
        signal_sl: float | None,
        signal_tp: float | None,
    ) -> tuple[float, float]:
        if signal_entry is None or signal_sl is None or signal_tp is None:
            raise ValueError("decisão de entrada sem SL/TP")
        sl_dist = abs(signal_entry - signal_sl)
        tp_dist = abs(signal_tp - signal_entry)
        if side == "buy":
            return entry - sl_dist, entry + tp_dist
        return entry + sl_dist, entry - tp_dist

    @staticmethod
    def _check_stops(
        position: _OpenPosition,
        bar: Bar,
    ) -> tuple[float, str] | None:
        if position.side == "buy":
            # Conservador: se SL e TP na mesma barra, assume SL primeiro
            if bar.low <= position.stop_loss:
                return position.stop_loss, "stop loss"
            if bar.high >= position.take_profit:
                return position.take_profit, "take profit"
        else:
            if bar.high >= position.stop_loss:
                return position.stop_loss, "stop loss"
            if bar.low <= position.take_profit:
                return position.take_profit, "take profit"
        return None

    def _pnl(self, position: _OpenPosition, exit_price: float) -> float:
        # money_at_risk_per_lot é |entry-stop| → usamos a mesma fórmula para |entry-exit|
        per_lot = money_at_risk_per_lot(
            position.entry_price,
            exit_price,
            tick_size=self.contract.tick_size,
            tick_value=self.contract.tick_value,
        )
        direction = 1.0 if position.side == "buy" else -1.0
        signed = direction * (exit_price - position.entry_price)
        # per_lot é sempre positivo para a distância; reaplica sinal
        if abs(exit_price - position.entry_price) < 1e-12:
            return 0.0
        raw = per_lot * position.volume
        return raw if signed > 0 else -raw
