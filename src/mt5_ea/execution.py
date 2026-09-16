"""Execução de decisões de trade (dry-run por padrão). Separado da estratégia."""

from __future__ import annotations

import logging
from typing import Any

from mt5_ea.connection import MT5Client
from mt5_ea.risk import TradeDecision

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Traduz TradeDecision → chamadas ao MT5Client (ou log em dry-run)."""

    def __init__(self, client: MT5Client, *, magic: int, dry_run: bool) -> None:
        self._client = client
        self._magic = magic
        self._dry_run = dry_run

    def execute(self, decision: TradeDecision, *, symbol: str) -> dict[str, Any]:
        if decision.action == "skip":
            logger.info("EXEC skip | %s", decision.reason)
            return {"status": "skipped", "reason": decision.reason}

        if decision.action in {"exit_long", "exit_short"}:
            side = "buy" if decision.action == "exit_long" else "sell"
            logger.info(
                "EXEC %s | dry_run=%s | %s",
                decision.action,
                self._dry_run,
                decision.reason,
            )
            return self._client.close_positions(
                symbol=symbol,
                side=side,
                magic=self._magic,
            )

        if decision.action in {"enter_long", "enter_short"}:
            if decision.volume is None or decision.stop_loss is None or decision.take_profit is None:
                logger.error("EXEC abortada: decisão de entrada incompleta: %s", decision)
                return {"status": "error", "reason": "decisão incompleta"}

            side = "buy" if decision.action == "enter_long" else "sell"
            logger.info(
                "EXEC %s | vol=%.2f SL=%.5f TP=%.5f dry_run=%s | %s",
                decision.action,
                decision.volume,
                decision.stop_loss,
                decision.take_profit,
                self._dry_run,
                decision.reason,
            )
            return self._client.place_market_order(
                symbol=symbol,
                order_type=side,
                volume=decision.volume,
                stop_loss=decision.stop_loss,
                take_profit=decision.take_profit,
                magic=self._magic,
                comment=f"mt5_ea:{decision.action}",
            )

        logger.warning("EXEC ação desconhecida: %s", decision.action)
        return {"status": "error", "reason": f"ação desconhecida: {decision.action}"}
