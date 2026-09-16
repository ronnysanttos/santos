"""Módulo de conexão com o terminal MetaTrader 5."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Self

from mt5_ea.config import Settings

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - ambiente sem pacote MT5 (ex.: Linux puro)
    mt5 = None  # type: ignore[assignment]


class MT5ConnectionError(RuntimeError):
    """Erro de inicialização, login ou operação no MetaTrader 5."""


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    login: int
    name: str
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    leverage: int
    trade_mode: int


@dataclass(frozen=True, slots=True)
class SymbolSnapshot:
    name: str
    bid: float
    ask: float
    point: float
    digits: int
    trade_mode: int
    volume_min: float
    volume_max: float


@dataclass(frozen=True, slots=True)
class TickSnapshot:
    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float
    volume: int


class MT5Client:
    """Cliente com initialize / login / info / shutdown gracioso."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def dry_run(self) -> bool:
        return self._settings.dry_run

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    def connect(self) -> None:
        """Inicializa o terminal e autentica com as credenciais do .env."""
        self._ensure_package()
        settings = self._settings
        settings.require_credentials()

        init_kwargs: dict[str, Any] = {
            "login": settings.login,
            "password": settings.password,
            "server": settings.server,
            "timeout": settings.timeout_ms,
        }
        if settings.mt5_path:
            init_kwargs["path"] = settings.mt5_path

        logger.info(
            "Inicializando MT5 (login=%s, server=%s, path=%s)",
            settings.login,
            settings.server,
            settings.mt5_path or "(padrão)",
        )

        if not mt5.initialize(**init_kwargs):
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Falha ao inicializar/login no MT5: ({code}) {message}"
            )

        self._connected = True
        account = self.get_account_info()
        logger.info(
            "Conectado: conta=%s | %s | saldo=%.2f %s | equity=%.2f",
            account.login,
            account.server,
            account.balance,
            account.currency,
            account.equity,
        )

    def shutdown(self) -> None:
        """Encerra a conexão com o terminal de forma segura."""
        if mt5 is None:
            self._connected = False
            return
        if self._connected or mt5.terminal_info() is not None:
            logger.info("Encerrando conexão MT5...")
            mt5.shutdown()
        self._connected = False

    def get_account_info(self) -> AccountSnapshot:
        self._require_connected()
        info = mt5.account_info()
        if info is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Não foi possível obter account_info: ({code}) {message}"
            )
        return AccountSnapshot(
            login=int(info.login),
            name=str(info.name),
            server=str(info.server),
            currency=str(info.currency),
            balance=float(info.balance),
            equity=float(info.equity),
            margin=float(info.margin),
            margin_free=float(info.margin_free),
            leverage=int(info.leverage),
            trade_mode=int(info.trade_mode),
        )

    def ensure_symbol(self, symbol: str | None = None) -> SymbolSnapshot:
        """Seleciona o símbolo no Market Watch e retorna informações básicas."""
        self._require_connected()
        name = (symbol or self._settings.symbol).upper()

        if not mt5.symbol_select(name, True):
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Falha ao selecionar símbolo {name}: ({code}) {message}"
            )

        info = mt5.symbol_info(name)
        tick = mt5.symbol_info_tick(name)
        if info is None or tick is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Sem dados para o símbolo {name}: ({code}) {message}"
            )

        return SymbolSnapshot(
            name=name,
            bid=float(tick.bid),
            ask=float(tick.ask),
            point=float(info.point),
            digits=int(info.digits),
            trade_mode=int(info.trade_mode),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
        )

    def get_tick(self, symbol: str | None = None) -> TickSnapshot:
        self._require_connected()
        name = (symbol or self._settings.symbol).upper()
        tick = mt5.symbol_info_tick(name)
        if tick is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Tick indisponível para {name}: ({code}) {message}"
            )
        return TickSnapshot(
            symbol=name,
            time=datetime.fromtimestamp(tick.time),
            bid=float(tick.bid),
            ask=float(tick.ask),
            last=float(tick.last),
            volume=int(tick.volume),
        )

    def get_rates(
        self,
        symbol: str | None = None,
        *,
        timeframe_minutes: int | None = None,
        count: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna as últimas N barras como lista de dicts legíveis."""
        self._require_connected()
        name = (symbol or self._settings.symbol).upper()
        minutes = timeframe_minutes or self._settings.timeframe_minutes
        bars = count or self._settings.bars
        tf = self._minutes_to_timeframe(minutes)

        rates = mt5.copy_rates_from_pos(name, tf, 0, bars)
        if rates is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Falha ao copiar rates de {name}: ({code}) {message}"
            )

        result: list[dict[str, Any]] = []
        for row in rates:
            result.append(
                {
                    "time": datetime.fromtimestamp(int(row["time"])),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "tick_volume": int(row["tick_volume"]),
                }
            )
        return result

    def place_market_order(
        self,
        *,
        symbol: str,
        order_type: str,
        volume: float,
        comment: str = "mt5_ea",
    ) -> dict[str, Any]:
        """
        Envia ordem a mercado — bloqueada por padrão quando dry_run=True.

        order_type: 'buy' ou 'sell'
        """
        self._require_connected()
        side = order_type.strip().lower()
        if side not in {"buy", "sell"}:
            raise ValueError("order_type deve ser 'buy' ou 'sell'")

        if self._settings.dry_run:
            logger.warning(
                "[DRY-RUN] Ordem NÃO enviada: %s %.2f %s (%s)",
                side.upper(),
                volume,
                symbol,
                comment,
            )
            return {
                "dry_run": True,
                "retcode": None,
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "comment": comment,
            }

        tick = self.get_tick(symbol)
        order_type_const = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "buy" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type_const,
            "price": price,
            "deviation": 20,
            "magic": 9327001,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(f"order_send falhou: ({code}) {message}")

        payload = {
            "dry_run": False,
            "retcode": int(result.retcode),
            "deal": int(getattr(result, "deal", 0) or 0),
            "order": int(getattr(result, "order", 0) or 0),
            "volume": float(getattr(result, "volume", volume) or volume),
            "price": float(getattr(result, "price", price) or price),
            "comment": str(getattr(result, "comment", comment) or comment),
            "symbol": symbol,
            "side": side,
        }
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("Ordem rejeitada: %s", payload)
        else:
            logger.info("Ordem executada: %s", payload)
        return payload

    @staticmethod
    def _minutes_to_timeframe(minutes: int) -> int:
        mapping = {
            1: mt5.TIMEFRAME_M1,
            2: mt5.TIMEFRAME_M2,
            3: mt5.TIMEFRAME_M3,
            4: mt5.TIMEFRAME_M4,
            5: mt5.TIMEFRAME_M5,
            6: mt5.TIMEFRAME_M6,
            10: mt5.TIMEFRAME_M10,
            12: mt5.TIMEFRAME_M12,
            15: mt5.TIMEFRAME_M15,
            20: mt5.TIMEFRAME_M20,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1,
            120: mt5.TIMEFRAME_H2,
            180: mt5.TIMEFRAME_H3,
            240: mt5.TIMEFRAME_H4,
            360: mt5.TIMEFRAME_H6,
            480: mt5.TIMEFRAME_H8,
            720: mt5.TIMEFRAME_H12,
            1440: mt5.TIMEFRAME_D1,
            10080: mt5.TIMEFRAME_W1,
            43200: mt5.TIMEFRAME_MN1,
        }
        if minutes not in mapping:
            raise ValueError(
                f"Timeframe {minutes} min não suportado. "
                f"Use um destes: {sorted(mapping)}"
            )
        return mapping[minutes]

    def _ensure_package(self) -> None:
        if mt5 is None:
            raise MT5ConnectionError(
                "Pacote MetaTrader5 não está instalado ou não é suportado "
                "nesta plataforma. Instale com: pip install MetaTrader5 "
                "(requer Windows ou Wine + terminal MT5)."
            )

    def _require_connected(self) -> None:
        self._ensure_package()
        if not self._connected:
            raise MT5ConnectionError("Cliente MT5 não está conectado. Chame connect().")
