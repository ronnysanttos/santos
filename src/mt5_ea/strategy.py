"""Sinais de trading — geração separada da execução de ordens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, Sequence

from mt5_ea.connection import TickSnapshot
from mt5_ea.indicators import atr, ema, value_at

SignalAction = Literal[
    "hold",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
]


@dataclass(frozen=True, slots=True)
class Signal:
    """Sinal gerado pela estratégia (ainda sem sizing / filtros de risco)."""

    action: SignalAction
    reason: str
    strength: float = 0.0
    ema_fast: float | None = None
    ema_slow: float | None = None
    atr: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


class Strategy(Protocol):
    def evaluate(
        self,
        tick: TickSnapshot,
        bars: Sequence[dict[str, Any]],
        *,
        open_side: str | None = None,
    ) -> Signal: ...


@dataclass(frozen=True, slots=True)
class DualEmaAtrParams:
    ema_fast: int = 12
    ema_slow: int = 26
    atr_period: int = 14
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 2.5

    def min_bars(self) -> int:
        # +2 para cruzamento (barra atual vs anterior) e ATR Wilder
        return max(self.ema_slow, self.atr_period + 1) + 2


class DualEmaAtrStrategy:
    """
    Filtro de tendência com duas EMAs + stops baseados em ATR.

    Entrada long: cruzamento EMA rápida acima da lenta (barra fechada).
    Entrada short: cruzamento EMA rápida abaixo da lenta.
    Saída: cruzamento contrário ao lado da posição aberta.

    SL/TP sugeridos: entry ± ATR * multiplicadores (a execução/risco confirma).
    """

    def __init__(self, params: DualEmaAtrParams | None = None) -> None:
        self.params = params or DualEmaAtrParams()

    def evaluate(
        self,
        tick: TickSnapshot,
        bars: Sequence[dict[str, Any]],
        *,
        open_side: str | None = None,
    ) -> Signal:
        p = self.params
        need = p.min_bars()
        if len(bars) < need:
            return Signal(
                action="hold",
                reason=f"barras insuficientes ({len(bars)}/{need})",
            )

        closes = [float(b["close"]) for b in bars]
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]

        ema_fast_s = ema(closes, p.ema_fast)
        ema_slow_s = ema(closes, p.ema_slow)
        atr_s = atr(highs, lows, closes, p.atr_period)

        i = len(bars) - 1
        # Usa a penúltima barra fechada para o cruzamento (evita sinal em candle incompleto
        # quando o feed inclui a barra em formação como última).
        sig_i = i - 1
        prev_i = sig_i - 1

        f0 = value_at(ema_fast_s, prev_i)
        s0 = value_at(ema_slow_s, prev_i)
        f1 = value_at(ema_fast_s, sig_i)
        s1 = value_at(ema_slow_s, sig_i)
        atr1 = value_at(atr_s, sig_i)

        if None in (f0, s0, f1, s1, atr1):
            return Signal(action="hold", reason="indicadores ainda aquecendo")

        assert f0 is not None and s0 is not None and f1 is not None and s1 is not None
        assert atr1 is not None

        cross_up = f0 <= s0 and f1 > s1
        cross_down = f0 >= s0 and f1 < s1
        strength = abs(f1 - s1) / atr1 if atr1 > 0 else 0.0

        side = (open_side or "").strip().lower() or None
        entry_long = float(tick.ask)
        entry_short = float(tick.bid)

        if side == "buy":
            if cross_down:
                return Signal(
                    action="exit_long",
                    reason=(
                        f"saída long: cruzamento bearish "
                        f"EMA{p.ema_fast}={f1:.5f} < EMA{p.ema_slow}={s1:.5f}"
                    ),
                    strength=strength,
                    ema_fast=f1,
                    ema_slow=s1,
                    atr=atr1,
                )
            return Signal(
                action="hold",
                reason=(
                    f"mantém long | EMA{p.ema_fast}={f1:.5f} "
                    f"EMA{p.ema_slow}={s1:.5f} ATR={atr1:.5f}"
                ),
                strength=strength,
                ema_fast=f1,
                ema_slow=s1,
                atr=atr1,
            )

        if side == "sell":
            if cross_up:
                return Signal(
                    action="exit_short",
                    reason=(
                        f"saída short: cruzamento bullish "
                        f"EMA{p.ema_fast}={f1:.5f} > EMA{p.ema_slow}={s1:.5f}"
                    ),
                    strength=strength,
                    ema_fast=f1,
                    ema_slow=s1,
                    atr=atr1,
                )
            return Signal(
                action="hold",
                reason=(
                    f"mantém short | EMA{p.ema_fast}={f1:.5f} "
                    f"EMA{p.ema_slow}={s1:.5f} ATR={atr1:.5f}"
                ),
                strength=strength,
                ema_fast=f1,
                ema_slow=s1,
                atr=atr1,
            )

        # Sem posição: só entra no cruzamento
        if cross_up:
            sl = entry_long - p.atr_sl_mult * atr1
            tp = entry_long + p.atr_tp_mult * atr1
            return Signal(
                action="enter_long",
                reason=(
                    f"entrada long: cruzamento bullish "
                    f"EMA{p.ema_fast}={f1:.5f} > EMA{p.ema_slow}={s1:.5f} | "
                    f"ATR={atr1:.5f} SL={sl:.5f} TP={tp:.5f}"
                ),
                strength=strength,
                ema_fast=f1,
                ema_slow=s1,
                atr=atr1,
                entry_price=entry_long,
                stop_loss=sl,
                take_profit=tp,
            )

        if cross_down:
            sl = entry_short + p.atr_sl_mult * atr1
            tp = entry_short - p.atr_tp_mult * atr1
            return Signal(
                action="enter_short",
                reason=(
                    f"entrada short: cruzamento bearish "
                    f"EMA{p.ema_fast}={f1:.5f} < EMA{p.ema_slow}={s1:.5f} | "
                    f"ATR={atr1:.5f} SL={sl:.5f} TP={tp:.5f}"
                ),
                strength=strength,
                ema_fast=f1,
                ema_slow=s1,
                atr=atr1,
                entry_price=entry_short,
                stop_loss=sl,
                take_profit=tp,
            )

        trend = "alta" if f1 > s1 else "baixa" if f1 < s1 else "neutro"
        return Signal(
            action="hold",
            reason=(
                f"sem cruzamento | tendência={trend} "
                f"EMA{p.ema_fast}={f1:.5f} EMA{p.ema_slow}={s1:.5f} ATR={atr1:.5f}"
            ),
            strength=strength,
            ema_fast=f1,
            ema_slow=s1,
            atr=atr1,
        )


# Compatibilidade: alias antigo usado nos testes iniciais
class PlaceholderStrategy:
    """Mantido para compatibilidade; preferir DualEmaAtrStrategy."""

    def evaluate(
        self,
        tick: TickSnapshot,
        bars: Sequence[dict[str, Any]],
        *,
        open_side: str | None = None,
    ) -> Signal:
        _ = tick, open_side
        if not bars:
            return Signal(action="hold", reason="sem barras")
        last_close = float(bars[-1]["close"])
        first_close = float(bars[0]["close"])
        change_pct = (
            ((last_close - first_close) / first_close) * 100.0 if first_close else 0.0
        )
        return Signal(
            action="hold",
            reason=f"placeholder: variação {change_pct:+.3f}% — sem ordem",
            strength=abs(change_pct),
        )

    # API legada
    def on_tick(
        self,
        tick: TickSnapshot,
        bars: list[dict[str, Any]],
    ) -> Signal:
        return self.evaluate(tick, bars)
