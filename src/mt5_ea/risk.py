"""Gestão de risco: sizing, filtros e validação de decisões (sem MT5)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal

from mt5_ea.strategy import Signal

logger = logging.getLogger(__name__)

DecisionAction = Literal[
    "skip",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
]


@dataclass(frozen=True, slots=True)
class RiskParams:
    mode: Literal["percent", "fixed"] = "percent"
    risk_percent: float = 0.5
    fixed_lots: float = 0.01
    max_positions: int = 1
    max_daily_loss_percent: float = 2.0  # 0 = desativado
    max_spread_points: float = 25.0  # 0 = desativado
    session_start_hour: int | None = 7  # None = sem filtro
    session_end_hour: int | None = 21  # exclusivo se start < end
    magic: int = 9327001


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """Especificação do contrato para sizing (preenchida a partir do símbolo MT5)."""

    point: float
    digits: int
    volume_min: float
    volume_max: float
    volume_step: float
    tick_size: float
    tick_value: float


@dataclass(frozen=True, slots=True)
class RiskContext:
    equity: float
    balance: float
    bid: float
    ask: float
    open_positions: int
    open_side: str | None  # 'buy' | 'sell' | None
    daily_pnl: float
    now: datetime
    contract: ContractSpec


@dataclass(frozen=True, slots=True)
class TradeDecision:
    action: DecisionAction
    reason: str
    volume: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    signal_strength: float = 0.0


def normalize_volume(
    volume: float,
    *,
    volume_min: float,
    volume_max: float,
    volume_step: float,
) -> float:
    """Arredonda volume para o step do símbolo e limita ao range permitido."""
    if volume_step <= 0:
        raise ValueError("volume_step deve ser > 0")
    steps = math.floor(volume / volume_step + 1e-12)
    rounded = steps * volume_step
    # corrige float drift
    decimals = max(0, min(8, int(round(-math.log10(volume_step))) if volume_step < 1 else 0))
    rounded = round(rounded, decimals)
    if rounded < volume_min:
        return 0.0
    return min(rounded, volume_max)


def money_at_risk_per_lot(
    entry: float,
    stop: float,
    *,
    tick_size: float,
    tick_value: float,
) -> float:
    """Perda aproximada em moeda da conta por 1.0 lote se o SL for atingido."""
    if tick_size <= 0 or tick_value <= 0:
        raise ValueError("tick_size e tick_value devem ser > 0")
    distance = abs(entry - stop)
    if distance <= 0:
        raise ValueError("distância entry/stop deve ser > 0")
    ticks = distance / tick_size
    return ticks * tick_value


def size_by_risk_percent(
    equity: float,
    risk_percent: float,
    entry: float,
    stop: float,
    contract: ContractSpec,
) -> float:
    if equity <= 0:
        return 0.0
    if risk_percent <= 0:
        return 0.0
    risk_money = equity * (risk_percent / 100.0)
    per_lot = money_at_risk_per_lot(
        entry,
        stop,
        tick_size=contract.tick_size,
        tick_value=contract.tick_value,
    )
    if per_lot <= 0:
        return 0.0
    raw = risk_money / per_lot
    return normalize_volume(
        raw,
        volume_min=contract.volume_min,
        volume_max=contract.volume_max,
        volume_step=contract.volume_step,
    )


def spread_points(bid: float, ask: float, point: float) -> float:
    if point <= 0:
        raise ValueError("point deve ser > 0")
    return (ask - bid) / point


def in_trading_session(
    now: datetime,
    start_hour: int | None,
    end_hour: int | None,
) -> bool:
    """
    Filtro de sessão por hora local do `now`.

    - Ambos None → sempre aberto
    - start < end → [start, end)
    - start > end → sessão que cruza meia-noite (ex.: 22→6)
    """
    if start_hour is None and end_hour is None:
        return True
    if start_hour is None or end_hour is None:
        raise ValueError("Defina SESSION_START e SESSION_END juntos, ou ambos vazios")
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        raise ValueError("horas de sessão devem estar entre 0 e 23")

    current = now.time()
    start_t = time(hour=start_hour)
    end_t = time(hour=end_hour)
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_t <= current < end_t
    # atravessa meia-noite
    return current >= start_t or current < end_t


class RiskManager:
    """Aplica filtros e sizing sobre um Signal → TradeDecision."""

    def __init__(self, params: RiskParams | None = None) -> None:
        self.params = params or RiskParams()

    def decide(self, signal: Signal, ctx: RiskContext) -> TradeDecision:
        p = self.params

        # 1) Perda diária
        if p.max_daily_loss_percent > 0 and ctx.balance > 0:
            loss_limit = ctx.balance * (p.max_daily_loss_percent / 100.0)
            if ctx.daily_pnl <= -loss_limit:
                decision = TradeDecision(
                    action="skip",
                    reason=(
                        f"bloqueado: perda diária {ctx.daily_pnl:.2f} "
                        f"atingiu limite -{loss_limit:.2f} "
                        f"({p.max_daily_loss_percent}% do balance)"
                    ),
                    signal_strength=signal.strength,
                )
                logger.info("RISCO skip | %s", decision.reason)
                return decision

        # 2) Sessão
        if not in_trading_session(ctx.now, p.session_start_hour, p.session_end_hour):
            decision = TradeDecision(
                action="skip",
                reason=(
                    f"fora da sessão "
                    f"({p.session_start_hour}:00–{p.session_end_hour}:00) "
                    f"agora={ctx.now.strftime('%H:%M')}"
                ),
                signal_strength=signal.strength,
            )
            # Saídas ainda devem ser permitidas mesmo fora da sessão
            if signal.action in {"exit_long", "exit_short"}:
                logger.info(
                    "RISCO: fora da sessão, mas permitindo saída | sinal=%s",
                    signal.action,
                )
            else:
                logger.info("RISCO skip | %s | sinal=%s (%s)", decision.reason, signal.action, signal.reason)
                return decision

        # 3) Saídas (não dependem de spread / max positions)
        if signal.action == "exit_long":
            if ctx.open_side != "buy":
                return TradeDecision(
                    action="skip",
                    reason="skip exit_long: não há posição long aberta",
                    signal_strength=signal.strength,
                )
            return TradeDecision(
                action="exit_long",
                reason=signal.reason,
                signal_strength=signal.strength,
            )
        if signal.action == "exit_short":
            if ctx.open_side != "sell":
                return TradeDecision(
                    action="skip",
                    reason="skip exit_short: não há posição short aberta",
                    signal_strength=signal.strength,
                )
            return TradeDecision(
                action="exit_short",
                reason=signal.reason,
                signal_strength=signal.strength,
            )

        if signal.action == "hold":
            return TradeDecision(
                action="skip",
                reason=f"sem entrada: {signal.reason}",
                signal_strength=signal.strength,
            )

        # 4) Entradas
        if signal.action not in {"enter_long", "enter_short"}:
            return TradeDecision(
                action="skip",
                reason=f"ação de sinal desconhecida: {signal.action}",
                signal_strength=signal.strength,
            )

        if ctx.open_positions >= p.max_positions:
            return TradeDecision(
                action="skip",
                reason=(
                    f"max posições atingido ({ctx.open_positions}/{p.max_positions})"
                ),
                signal_strength=signal.strength,
            )

        if ctx.open_side is not None:
            return TradeDecision(
                action="skip",
                reason=f"já existe posição {ctx.open_side}; aguarde saída",
                signal_strength=signal.strength,
            )

        if p.max_spread_points > 0:
            sp = spread_points(ctx.bid, ctx.ask, ctx.contract.point)
            if sp > p.max_spread_points:
                return TradeDecision(
                    action="skip",
                    reason=(
                        f"spread alto ({sp:.1f} > {p.max_spread_points:.1f} pontos)"
                    ),
                    signal_strength=signal.strength,
                )

        entry = signal.entry_price
        sl = signal.stop_loss
        tp = signal.take_profit
        if entry is None or sl is None or tp is None:
            return TradeDecision(
                action="skip",
                reason="sinal de entrada sem entry/SL/TP",
                signal_strength=signal.strength,
            )

        if signal.action == "enter_long" and not (sl < entry < tp):
            return TradeDecision(
                action="skip",
                reason=f"SL/TP inválidos para long (SL={sl} entry={entry} TP={tp})",
                signal_strength=signal.strength,
            )
        if signal.action == "enter_short" and not (tp < entry < sl):
            return TradeDecision(
                action="skip",
                reason=f"SL/TP inválidos para short (TP={tp} entry={entry} SL={sl})",
                signal_strength=signal.strength,
            )

        volume = self._size(entry=entry, stop=sl, ctx=ctx)
        if volume <= 0:
            return TradeDecision(
                action="skip",
                reason="volume calculado abaixo do mínimo do símbolo",
                signal_strength=signal.strength,
            )

        action: DecisionAction = (
            "enter_long" if signal.action == "enter_long" else "enter_short"
        )
        decision = TradeDecision(
            action=action,
            reason=signal.reason,
            volume=volume,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            signal_strength=signal.strength,
        )
        logger.info(
            "RISCO ok | %s vol=%.2f entry=%.5f SL=%.5f TP=%.5f | %s",
            action,
            volume,
            entry,
            sl,
            tp,
            signal.reason,
        )
        return decision

    def _size(self, *, entry: float, stop: float, ctx: RiskContext) -> float:
        p = self.params
        if p.mode == "fixed":
            return normalize_volume(
                p.fixed_lots,
                volume_min=ctx.contract.volume_min,
                volume_max=ctx.contract.volume_max,
                volume_step=ctx.contract.volume_step,
            )
        return size_by_risk_percent(
            ctx.equity,
            p.risk_percent,
            entry,
            stop,
            ctx.contract,
        )
