"""Carregadores de OHLC: CSV, sintético e (opcional) MetaTrader 5."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "tick_volume": int(self.volume),
        }


def bars_to_dicts(bars: Sequence[Bar]) -> list[dict[str, Any]]:
    return [b.as_dict() for b in bars]


def load_csv(path: str | Path) -> list[Bar]:
    """
    CSV com cabeçalho: time,open,high,low,close[,volume]

    `time` aceita ISO-8601 ou `YYYY-MM-DD HH:MM:SS`.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"CSV não encontrado: {file_path}")

    bars: list[Bar] = []
    with file_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"time", "open", "high", "low", "close"}
        if reader.fieldnames is None or not required.issubset(
            {f.strip().lower() for f in reader.fieldnames}
        ):
            raise ValueError(
                "CSV precisa das colunas: time,open,high,low,close[,volume]"
            )

        # normaliza nomes
        field_map = {f.strip().lower(): f for f in reader.fieldnames}

        for row in reader:
            raw_time = row[field_map["time"]].strip()
            ts = _parse_time(raw_time)
            o = float(row[field_map["open"]])
            h = float(row[field_map["high"]])
            low = float(row[field_map["low"]])
            c = float(row[field_map["close"]])
            vol_key = field_map.get("volume") or field_map.get("tick_volume")
            vol = float(row[vol_key]) if vol_key and row.get(vol_key) else 0.0
            if h < max(o, c) or low > min(o, c):
                h = max(h, o, c)
                low = min(low, o, c)
            bars.append(Bar(time=ts, open=o, high=h, low=low, close=c, volume=vol))

    if len(bars) < 2:
        raise ValueError("CSV precisa de pelo menos 2 barras")
    return bars


def generate_synthetic_ohlc(
    *,
    bars: int = 300,
    start: datetime | None = None,
    timeframe_minutes: int = 15,
    start_price: float = 1.1000,
    seed: int = 42,
) -> list[Bar]:
    """
    Gera OHLC sintético com tendência de baixa → alta → baixa.

    Útil para demos/CI sem MT5; produz cruzamentos EMA previsíveis.
    """
    if bars < 50:
        raise ValueError("generate_synthetic_ohlc requer bars >= 50")

    t0 = start or datetime(2024, 1, 2, 8, 0, 0)
    # PRNG simples determinístico (LCG) — evita dependência de numpy/random state global
    state = seed & 0xFFFFFFFF

    def rnd() -> float:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state / 0xFFFFFFFF

    third = bars // 3
    closes: list[float] = []
    price = start_price
    for i in range(bars):
        if i < third:
            drift = -0.00035
        elif i < 2 * third:
            drift = 0.00045
        else:
            drift = -0.00030
        noise = (rnd() - 0.5) * 0.0004
        price = max(0.5, price + drift + noise)
        closes.append(price)

    out: list[Bar] = []
    prev = start_price
    for i, close in enumerate(closes):
        open_ = prev
        swing = abs(close - open_) + 0.00015 + rnd() * 0.0002
        high = max(open_, close) + swing * 0.35
        low = min(open_, close) - swing * 0.35
        out.append(
            Bar(
                time=t0 + timedelta(minutes=timeframe_minutes * i),
                open=round(open_, 5),
                high=round(high, 5),
                low=round(low, 5),
                close=round(close, 5),
                volume=100 + int(rnd() * 50),
            )
        )
        prev = close
    return out


def load_mt5_history(
    symbol: str,
    *,
    timeframe_minutes: int = 15,
    bars: int = 500,
    settings: Any | None = None,
) -> list[Bar]:
    """
    Busca histórico no terminal MT5 (opcional).

    Requer pacote MetaTrader5 + terminal disponível. Em CI/Linux costuma falhar —
    use CSV ou `--synthetic` nesse caso.
    """
    from mt5_ea.config import Settings, load_settings
    from mt5_ea.connection import MT5Client

    cfg: Settings = settings if settings is not None else load_settings()
    cfg = cfg.with_overrides(symbol=symbol)

    with MT5Client(cfg) as client:
        rows = client.get_rates(
            symbol,
            timeframe_minutes=timeframe_minutes,
            count=bars,
        )

    return [
        Bar(
            time=row["time"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("tick_volume", 0)),
        )
        for row in rows
    ]


def _parse_time(raw: str) -> datetime:
    raw = raw.strip()
    if raw.endswith("Z"):
        raw = raw[:-1]
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    # timestamp epoch?
    try:
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts)
    except ValueError as exc:
        raise ValueError(f"formato de time inválido: {raw!r}") from exc


def default_fx_contract() -> dict[str, float]:
    """Spec padrão estilo EURUSD para backtests offline."""
    return {
        "point": 0.00001,
        "digits": 5,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "spread_points": 10.0,
    }


def assert_ohlc_sane(bars: Sequence[Bar]) -> None:
    for i, bar in enumerate(bars):
        if not (bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError(f"OHLC inconsistente na barra {i}: {bar}")
        if math.isnan(bar.close):
            raise ValueError(f"NaN na barra {i}")
