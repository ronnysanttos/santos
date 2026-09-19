from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ia_financeira.config import Settings, settings
from ia_financeira.mt5.client import MT5Client, MT5UnavailableError
from ia_financeira.mt5.indicators import atr, last_valid, rsi, sma


@dataclass
class MarketSnapshot:
    ticker: str
    mode: str
    rsi_14: float
    ma_200: float
    price_vs_ma200: str
    atr_14: float
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    digits: int = 5
    bars: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_context_block(self) -> str:
        rsi_label = ""
        if self.rsi_14 <= 30:
            rsi_label = " (Sobrevendido)"
        elif self.rsi_14 >= 70:
            rsi_label = " (Sobrecomprado)"
        return (
            f"[DADOS MT5/MERCADO ({self.mode})]: ticker={self.ticker}, "
            f"bid={self.bid}, ask={self.ask}, last={self.last}, "
            f"RSI_14={self.rsi_14:.2f}{rsi_label}, "
            f"MA_200={self.ma_200:.5f} ({self.price_vs_ma200}), "
            f"ATR_14={self.atr_14:.5f}. {self.note}"
        )


def _price_vs_ma(price: float, ma: float) -> str:
    if ma <= 0 or price <= 0:
        return "flat"
    if price > ma * 1.001:
        return "Acima da Média"
    if price < ma * 0.999:
        return "Abaixo da Média"
    return "flat"


class MarketDataProvider:
    """
    Snapshot de mercado: MT5 real (Windows) ou stub (Linux/CI).
    MARKET_DATA_MODE=auto tenta MT5 e faz fallback para stub.
    """

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings

    def snapshot(self, ticker: str) -> MarketSnapshot:
        mode = self.cfg.market_data_mode
        symbol = ticker.upper().strip()
        if mode == "stub":
            return self._stub(symbol)
        if mode in {"mt5", "auto"}:
            try:
                return self._from_mt5(symbol)
            except Exception as exc:  # noqa: BLE001 - graceful fallback
                if mode == "mt5":
                    return MarketSnapshot(
                        ticker=symbol,
                        mode="mt5-unavailable-fallback-stub",
                        rsi_14=50.0,
                        ma_200=0.0,
                        price_vs_ma200="flat",
                        atr_14=1.0,
                        note=f"MT5 falhou ({exc}); usando stub neutro.",
                    )
                stub = self._stub(symbol)
                stub.mode = "stub-fallback"
                stub.note = f"MT5 indisponível ({exc}); {stub.note}"
                return stub
        return self._stub(symbol)

    def _from_mt5(self, symbol: str) -> MarketSnapshot:
        client = MT5Client(self.cfg)
        try:
            client.connect()
            quote = client.ensure_symbol(symbol)
            bars = client.get_rates(symbol)
            closes = [b.close for b in bars]
            highs = [b.high for b in bars]
            lows = [b.low for b in bars]

            rsi_series = rsi(closes, self.cfg.mt5_rsi_period)
            ma_series = sma(closes, self.cfg.mt5_ma_period)
            atr_series = atr(highs, lows, closes, self.cfg.mt5_atr_period)

            rsi_v = last_valid(rsi_series)
            ma_v = last_valid(ma_series)
            atr_v = last_valid(atr_series)
            if rsi_v is None or ma_v is None or atr_v is None:
                raise MT5UnavailableError(
                    f"Barras insuficientes para indicadores "
                    f"(precisa ~{max(self.cfg.mt5_ma_period, self.cfg.mt5_atr_period + 1)})"
                )

            last_price = closes[-1]
            return MarketSnapshot(
                ticker=symbol,
                mode="mt5",
                rsi_14=round(rsi_v, 2),
                ma_200=round(ma_v, 5),
                price_vs_ma200=_price_vs_ma(last_price, ma_v),
                atr_14=round(atr_v, 5),
                bid=quote.bid,
                ask=quote.ask,
                last=quote.last or last_price,
                digits=quote.digits,
                bars=len(bars),
                note="Indicadores calculados a partir de barras reais do MetaTrader 5.",
            )
        finally:
            client.shutdown()

    def _stub(self, symbol: str) -> MarketSnapshot:
        # Didático alinhado ao exemplo do plano (RSI oversold).
        price = 48.50
        ma = 49.20
        return MarketSnapshot(
            ticker=symbol,
            mode="stub",
            rsi_14=28.0,
            ma_200=ma,
            price_vs_ma200=_price_vs_ma(price, ma),
            atr_14=1.25,
            bid=price - 0.01,
            ask=price + 0.01,
            last=price,
            digits=2,
            bars=220,
            note="Snapshot sintético (stub) para CI/Linux sem terminal MT5.",
        )
