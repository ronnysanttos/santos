"""Hook de estratégia placeholder — sem lógica de trading ao vivo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from mt5_ea.connection import TickSnapshot


@dataclass(frozen=True, slots=True)
class Signal:
    """Sinal simples gerado pela estratégia."""

    action: str  # 'hold' | 'buy' | 'sell'
    reason: str
    strength: float = 0.0


class Strategy(Protocol):
    def on_tick(
        self,
        tick: TickSnapshot,
        bars: list[dict[str, Any]],
    ) -> Signal: ...


class PlaceholderStrategy:
    """
    Estratégia de exemplo: sempre retorna 'hold'.

    Substitua `on_tick` pela sua lógica (médias móveis, breakout, etc.).
    Em dry-run o EA apenas registra o sinal sem enviar ordens.
    """

    def on_tick(
        self,
        tick: TickSnapshot,
        bars: list[dict[str, Any]],
    ) -> Signal:
        _ = tick
        if not bars:
            return Signal(action="hold", reason="sem barras", strength=0.0)

        last_close = float(bars[-1]["close"])
        first_close = float(bars[0]["close"])
        change_pct = ((last_close - first_close) / first_close) * 100.0 if first_close else 0.0

        return Signal(
            action="hold",
            reason=(
                f"placeholder: variação {change_pct:+.3f}% "
                f"nas últimas {len(bars)} barras — sem ordem"
            ),
            strength=abs(change_pct),
        )
