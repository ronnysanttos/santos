"""Carrega configuração a partir de variáveis de ambiente / arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

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


def _env_optional_hour(name: str, default: int | None) -> int | None:
    """Hora 0–23; string vazia desativa o filtro de sessão."""
    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    if stripped == "":
        return None
    hour = int(stripped)
    if hour < 0 or hour > 23:
        raise ValueError(f"{name} deve ser 0–23 ou vazio (desativado)")
    return hour


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

    # Estratégia Dual EMA + ATR
    ema_fast: int
    ema_slow: int
    atr_period: int
    atr_sl_mult: float
    atr_tp_mult: float

    # Risco
    risk_mode: Literal["percent", "fixed"]
    risk_percent: float
    fixed_lots: float
    max_positions: int
    max_daily_loss_percent: float
    max_spread_points: float
    session_start_hour: int | None
    session_end_hour: int | None
    magic: int

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

    def with_overrides(
        self,
        *,
        symbol: str | None = None,
        dry_run: bool | None = None,
    ) -> Settings:
        return replace(
            self,
            symbol=(symbol or self.symbol).strip().upper(),
            dry_run=self.dry_run if dry_run is None else dry_run,
        )


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Carrega `.env` (se existir) e monta Settings."""
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    path_raw = os.getenv("MT5_PATH", "").strip()
    risk_mode_raw = os.getenv("RISK_MODE", "percent").strip().lower()
    if risk_mode_raw not in {"percent", "fixed"}:
        raise ValueError("RISK_MODE deve ser 'percent' ou 'fixed'")

    ema_fast = _env_int("STRATEGY_EMA_FAST", 12)
    ema_slow = _env_int("STRATEGY_EMA_SLOW", 26)
    if ema_fast < 1 or ema_slow < 1:
        raise ValueError("períodos EMA devem ser >= 1")
    if ema_fast >= ema_slow:
        raise ValueError("STRATEGY_EMA_FAST deve ser menor que STRATEGY_EMA_SLOW")

    atr_period = _env_int("STRATEGY_ATR_PERIOD", 14)
    min_bars_needed = max(ema_slow, atr_period + 1) + 5
    bars = _env_int("MT5_BARS", max(100, min_bars_needed))
    if bars < min_bars_needed:
        bars = min_bars_needed

    return Settings(
        mt5_path=path_raw or None,
        login=_env_int("MT5_LOGIN", 0),
        password=os.getenv("MT5_PASSWORD", "").strip(),
        server=os.getenv("MT5_SERVER", "").strip(),
        timeout_ms=_env_int("MT5_TIMEOUT_MS", 60_000),
        symbol=os.getenv("MT5_SYMBOL", "EURUSD").strip().upper(),
        timeframe_minutes=_env_int("MT5_TIMEFRAME_MINUTES", 15),
        bars=bars,
        poll_interval_sec=_env_float("MT5_POLL_INTERVAL_SEC", 5.0),
        dry_run=_env_bool("MT5_DRY_RUN", True),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        atr_period=atr_period,
        atr_sl_mult=_env_float("STRATEGY_ATR_SL_MULT", 1.5),
        atr_tp_mult=_env_float("STRATEGY_ATR_TP_MULT", 2.5),
        risk_mode=risk_mode_raw,  # type: ignore[arg-type]
        risk_percent=_env_float("RISK_PERCENT", 0.5),
        fixed_lots=_env_float("RISK_FIXED_LOTS", 0.01),
        max_positions=_env_int("RISK_MAX_POSITIONS", 1),
        max_daily_loss_percent=_env_float("RISK_MAX_DAILY_LOSS_PERCENT", 2.0),
        max_spread_points=_env_float("RISK_MAX_SPREAD_POINTS", 25.0),
        session_start_hour=_env_optional_hour("RISK_SESSION_START_HOUR", 7),
        session_end_hour=_env_optional_hour("RISK_SESSION_END_HOUR", 21),
        magic=_env_int("RISK_MAGIC", 9327001),
    )
