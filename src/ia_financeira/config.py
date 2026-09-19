from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    return int(raw)


@dataclass(frozen=True)
class Settings:
    # Locked defaults (Rony): qwen2.5:7b + DuckDuckGo
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_temperature: float = 0.2
    ollama_allow_fallback: bool = True
    web_search_max_results: int = 5
    web_search_backend: str = "duckduckgo"
    min_confidence: int = 70
    daily_loss_limit_brl: float = 300.0
    high_impact_pause_minutes: int = 15
    # auto = tenta MT5 e cai para stub; stub | mt5
    market_data_mode: str = "auto"
    mt5_dry_run: bool = True
    # Exige MT5_DRY_RUN=false E este flag true para enviar ordem real (demo).
    mt5_allow_demo_orders: bool = False
    default_ticker: str = "PETR4"
    mt5_path: str = ""
    mt5_login: int | None = None
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_timeout_ms: int = 60000
    mt5_timeframe_minutes: int = 15
    mt5_bars: int = 220
    mt5_volume: float = 0.01
    mt5_sl_atr_mult: float = 1.5
    mt5_tp_atr_mult: float = 2.5
    mt5_magic: int = 20260919
    mt5_rsi_period: int = 14
    mt5_ma_period: int = 200
    mt5_atr_period: int = 14

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            ollama_temperature=_env_float("OLLAMA_TEMPERATURE", 0.2),
            ollama_allow_fallback=_env_bool("OLLAMA_ALLOW_FALLBACK", True),
            web_search_max_results=_env_int("WEB_SEARCH_MAX_RESULTS", 5),
            web_search_backend=os.getenv("WEB_SEARCH_BACKEND", "duckduckgo").lower(),
            min_confidence=_env_int("MIN_CONFIDENCE", 70),
            daily_loss_limit_brl=_env_float("DAILY_LOSS_LIMIT_BRL", 300.0),
            high_impact_pause_minutes=_env_int("HIGH_IMPACT_PAUSE_MINUTES", 15),
            market_data_mode=os.getenv("MARKET_DATA_MODE", "auto").lower(),
            mt5_dry_run=_env_bool("MT5_DRY_RUN", True),
            mt5_allow_demo_orders=_env_bool("MT5_ALLOW_DEMO_ORDERS", False),
            default_ticker=os.getenv("DEFAULT_TICKER", "PETR4"),
            mt5_path=os.getenv("MT5_PATH", "").strip(),
            mt5_login=_env_optional_int("MT5_LOGIN"),
            mt5_password=os.getenv("MT5_PASSWORD", ""),
            mt5_server=os.getenv("MT5_SERVER", "").strip(),
            mt5_timeout_ms=_env_int("MT5_TIMEOUT_MS", 60000),
            mt5_timeframe_minutes=_env_int("MT5_TIMEFRAME_MINUTES", 15),
            mt5_bars=_env_int("MT5_BARS", 220),
            mt5_volume=_env_float("MT5_VOLUME", 0.01),
            mt5_sl_atr_mult=_env_float("MT5_SL_ATR_MULT", 1.5),
            mt5_tp_atr_mult=_env_float("MT5_TP_ATR_MULT", 2.5),
            mt5_magic=_env_int("MT5_MAGIC", 20260919),
            mt5_rsi_period=_env_int("MT5_RSI_PERIOD", 14),
            mt5_ma_period=_env_int("MT5_MA_PERIOD", 200),
            mt5_atr_period=_env_int("MT5_ATR_PERIOD", 14),
        )

    def can_send_mt5_orders(self) -> bool:
        """Ordens reais só com dry-run desligado E flag demo explícita."""
        return (not self.mt5_dry_run) and self.mt5_allow_demo_orders


settings = Settings.from_env()
