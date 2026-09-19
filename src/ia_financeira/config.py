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


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_temperature: float = 0.2
    ollama_allow_fallback: bool = True
    web_search_max_results: int = 5
    web_search_backend: str = "duckduckgo"
    min_confidence: int = 70
    daily_loss_limit_brl: float = 300.0
    high_impact_pause_minutes: int = 15
    market_data_mode: str = "stub"
    mt5_dry_run: bool = True
    default_ticker: str = "PETR4"

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
            market_data_mode=os.getenv("MARKET_DATA_MODE", "stub").lower(),
            mt5_dry_run=_env_bool("MT5_DRY_RUN", True),
            default_ticker=os.getenv("DEFAULT_TICKER", "PETR4"),
        )


settings = Settings.from_env()
