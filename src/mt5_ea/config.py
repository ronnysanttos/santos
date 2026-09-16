"""Carrega configuração a partir de variáveis de ambiente / arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "sim"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração tipada do projeto (sem segredos hardcoded)."""

    mt5_path: str | None
    login: int
    password: str
    server: str
    timeout_ms: int
    symbol: str
    timeframe_minutes: int
    bars: int
    poll_interval_sec: float
    dry_run: bool

    def require_credentials(self) -> None:
        """Valida campos obrigatórios para login."""
        missing: list[str] = []
        if not self.login:
            missing.append("MT5_LOGIN")
        if not self.password or self.password == "sua_senha_aqui":
            missing.append("MT5_PASSWORD")
        if not self.server:
            missing.append("MT5_SERVER")
        if missing:
            raise ValueError(
                "Credenciais incompletas ou placeholder no .env: "
                + ", ".join(missing)
                + ". Copie .env.example para .env e preencha os valores."
            )


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Carrega `.env` (se existir) e monta Settings."""
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    path_raw = os.getenv("MT5_PATH", "").strip()
    return Settings(
        mt5_path=path_raw or None,
        login=_env_int("MT5_LOGIN", 0),
        password=os.getenv("MT5_PASSWORD", "").strip(),
        server=os.getenv("MT5_SERVER", "").strip(),
        timeout_ms=_env_int("MT5_TIMEOUT_MS", 60_000),
        symbol=os.getenv("MT5_SYMBOL", "EURUSD").strip().upper(),
        timeframe_minutes=_env_int("MT5_TIMEFRAME_MINUTES", 5),
        bars=_env_int("MT5_BARS", 20),
        poll_interval_sec=_env_float("MT5_POLL_INTERVAL_SEC", 5.0),
        dry_run=_env_bool("MT5_DRY_RUN", True),
    )
