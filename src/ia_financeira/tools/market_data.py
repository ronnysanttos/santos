from __future__ import annotations

from dataclasses import asdict, dataclass

from ia_financeira.config import Settings, settings


@dataclass
class MarketSnapshot:
    ticker: str
    mode: str
    rsi_14: float
    price_vs_ma200: str  # above | below | flat
    atr_14: float
    note: str

    def to_dict(self) -> dict:
        return asdict(self)

    def as_context_block(self) -> str:
        return (
            f"[DADOS MERCADO ({self.mode})]: ticker={self.ticker}, "
            f"RSI_14={self.rsi_14}, Média_200={self.price_vs_ma200}, "
            f"ATR_14={self.atr_14}. {self.note}"
        )


class MarketDataProvider:
    """
    Stub de indicadores para o MVP (Fase 1–2).
    Na Fase 3, trocar por leitura real via MetaTrader5.
    """

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings

    def snapshot(self, ticker: str) -> MarketSnapshot:
        mode = self.cfg.market_data_mode
        if mode == "mt5":
            # Placeholder: ambiente Linux/cloud tipicamente sem terminal MT5.
            return MarketSnapshot(
                ticker=ticker,
                mode="mt5-unavailable-fallback-stub",
                rsi_14=50.0,
                price_vs_ma200="flat",
                atr_14=1.0,
                note="MT5 não disponível neste ambiente; usando stub.",
            )
        # Stub didático alinhado ao exemplo do plano diretor (RSI oversold).
        return MarketSnapshot(
            ticker=ticker,
            mode="stub",
            rsi_14=28.0,
            price_vs_ma200="Acima do Preço Atual",
            atr_14=1.25,
            note="Snapshot sintético para o vertical slice (substituir na Fase 3).",
        )
