"""Dry-run / demo order execution path."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from ia_financeira.config import Settings, settings
from ia_financeira.mt5.client import MT5Client, MT5UnavailableError
from ia_financeira.tools.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


@dataclass
class OrderIntent:
    symbol: str
    side: str  # buy | sell
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    magic: int
    comment: str
    confidence: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_order_intent(
    *,
    action: str,
    snapshot: MarketSnapshot,
    confidence: int,
    cfg: Settings | None = None,
) -> OrderIntent | None:
    """Monta intenção de ordem a partir de COMPRA/VENDA + indicadores."""
    cfg = cfg or settings
    if action not in {"COMPRA", "VENDA"}:
        return None

    side = "buy" if action == "COMPRA" else "sell"
    price = snapshot.ask if side == "buy" else snapshot.bid
    if price <= 0:
        price = snapshot.last or 0.0
    atr = snapshot.atr_14 if snapshot.atr_14 > 0 else 1.0
    if side == "buy":
        sl = price - atr * cfg.mt5_sl_atr_mult
        tp = price + atr * cfg.mt5_tp_atr_mult
    else:
        sl = price + atr * cfg.mt5_sl_atr_mult
        tp = price - atr * cfg.mt5_tp_atr_mult

    return OrderIntent(
        symbol=snapshot.ticker,
        side=side,
        volume=cfg.mt5_volume,
        entry_price=round(price, snapshot.digits or 5),
        stop_loss=round(sl, snapshot.digits or 5),
        take_profit=round(tp, snapshot.digits or 5),
        magic=cfg.mt5_magic,
        comment="ia_financeira",
        confidence=confidence,
        dry_run=not cfg.can_send_mt5_orders(),
    )


class OrderExecutor:
    """Loga intenção em dry-run; só envia se Settings.can_send_mt5_orders()."""

    def __init__(self, cfg: Settings | None = None, client: MT5Client | None = None) -> None:
        self.cfg = cfg or settings
        self._client = client

    def execute(self, intent: OrderIntent | None) -> dict[str, Any]:
        if intent is None:
            return {"status": "skipped", "reason": "sem intenção de ordem"}

        if not self.cfg.can_send_mt5_orders() or intent.dry_run:
            logger.info(
                "DRY-RUN ORDER %s %s vol=%.2f entry=%.5f SL=%.5f TP=%.5f conf=%s",
                intent.side.upper(),
                intent.symbol,
                intent.volume,
                intent.entry_price,
                intent.stop_loss,
                intent.take_profit,
                intent.confidence,
            )
            return {
                "status": "dry_run",
                "message": "Ordem apenas registrada (dry-run). Nada enviado ao MT5.",
                "intent": intent.to_dict(),
                "would_send": True,
            }

        client = self._client
        owned = False
        try:
            if client is None:
                client = MT5Client(self.cfg)
                client.connect()
                owned = True
            result = client.place_market_order(
                symbol=intent.symbol,
                side=intent.side,
                volume=intent.volume,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                magic=intent.magic,
                comment=intent.comment,
            )
            result["intent"] = intent.to_dict()
            result["status"] = result.get("status", "sent")
            return result
        except MT5UnavailableError as exc:
            return {
                "status": "error",
                "error": str(exc),
                "intent": intent.to_dict(),
            }
        finally:
            if owned and client is not None:
                client.shutdown()
