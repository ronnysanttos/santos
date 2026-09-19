"""Cliente MetaTrader 5 com fallback gracioso (Linux/CI sem pacote/terminal)."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Self

from ia_financeira.config import Settings, settings

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - Linux/CI
    mt5 = None  # type: ignore[assignment]


class MT5UnavailableError(RuntimeError):
    """Pacote ou terminal MT5 indisponível neste ambiente."""


@dataclass(frozen=True)
class AccountInfo:
    login: int
    name: str
    server: str
    currency: str
    balance: float
    equity: float
    trade_mode: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SymbolQuote:
    name: str
    bid: float
    ask: float
    last: float
    point: float
    digits: int
    volume_min: float
    volume_max: float
    volume_step: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


def mt5_package_available() -> bool:
    return mt5 is not None


class MT5Client:
    """initialize / login / rates / symbol — sem enviar ordens aqui."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

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
        self._ensure_package()
        init_kwargs: dict[str, Any] = {"timeout": self.cfg.mt5_timeout_ms}
        if self.cfg.mt5_path:
            init_kwargs["path"] = self.cfg.mt5_path
        if self.cfg.mt5_login is not None and self.cfg.mt5_password and self.cfg.mt5_server:
            init_kwargs.update(
                {
                    "login": self.cfg.mt5_login,
                    "password": self.cfg.mt5_password,
                    "server": self.cfg.mt5_server,
                }
            )

        logger.info(
            "Inicializando MT5 (login=%s, server=%s)",
            self.cfg.mt5_login,
            self.cfg.mt5_server or "(terminal já logado)",
        )
        if not mt5.initialize(**init_kwargs):
            code, message = mt5.last_error()
            raise MT5UnavailableError(
                f"Falha ao inicializar MT5: ({code}) {message}"
            )
        self._connected = True

    def shutdown(self) -> None:
        if mt5 is None:
            self._connected = False
            return
        if self._connected or mt5.terminal_info() is not None:
            mt5.shutdown()
        self._connected = False

    def get_account_info(self) -> AccountInfo:
        self._require_connected()
        info = mt5.account_info()
        if info is None:
            code, message = mt5.last_error()
            raise MT5UnavailableError(f"account_info falhou: ({code}) {message}")
        return AccountInfo(
            login=int(info.login),
            name=str(info.name),
            server=str(info.server),
            currency=str(info.currency),
            balance=float(info.balance),
            equity=float(info.equity),
            trade_mode=int(info.trade_mode),
        )

    def ensure_symbol(self, symbol: str) -> SymbolQuote:
        self._require_connected()
        name = symbol.upper().strip()
        if not mt5.symbol_select(name, True):
            code, message = mt5.last_error()
            raise MT5UnavailableError(
                f"Falha ao selecionar símbolo {name}: ({code}) {message}"
            )
        info = mt5.symbol_info(name)
        tick = mt5.symbol_info_tick(name)
        if info is None or tick is None:
            code, message = mt5.last_error()
            raise MT5UnavailableError(
                f"Sem dados para {name}: ({code}) {message}"
            )
        return SymbolQuote(
            name=name,
            bid=float(tick.bid),
            ask=float(tick.ask),
            last=float(tick.last),
            point=float(info.point),
            digits=int(info.digits),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
            volume_step=float(info.volume_step) or float(info.volume_min) or 0.01,
        )

    def get_rates(
        self,
        symbol: str,
        *,
        timeframe_minutes: int | None = None,
        count: int | None = None,
    ) -> list[Bar]:
        self._require_connected()
        name = symbol.upper().strip()
        minutes = timeframe_minutes or self.cfg.mt5_timeframe_minutes
        bars = count or self.cfg.mt5_bars
        tf = self._minutes_to_timeframe(minutes)
        if not mt5.symbol_select(name, True):
            code, message = mt5.last_error()
            raise MT5UnavailableError(
                f"Falha ao selecionar símbolo {name}: ({code}) {message}"
            )
        rates = mt5.copy_rates_from_pos(name, tf, 0, bars)
        if rates is None or len(rates) == 0:
            code, message = mt5.last_error()
            raise MT5UnavailableError(
                f"Sem barras para {name}: ({code}) {message}"
            )
        result: list[Bar] = []
        for row in rates:
            result.append(
                Bar(
                    time=datetime.fromtimestamp(int(row["time"])),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    tick_volume=int(row["tick_volume"]),
                )
            )
        return result

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        magic: int,
        comment: str = "ia_financeira",
    ) -> dict[str, Any]:
        """Envia ordem a mercado. Chamador deve garantir can_send_mt5_orders()."""
        self._require_connected()
        quote = self.ensure_symbol(symbol)
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        price = quote.ask if side == "buy" else quote.bid
        filling = self._filling_mode(mt5.symbol_info(quote.name))
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": quote.name,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": 20,
            "magic": int(magic),
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            return {"status": "error", "error": f"({code}) {message}", "request": request}
        return {
            "status": "sent",
            "retcode": int(result.retcode),
            "deal": int(getattr(result, "deal", 0) or 0),
            "order": int(getattr(result, "order", 0) or 0),
            "ok": int(result.retcode) == mt5.TRADE_RETCODE_DONE,
            "request": request,
        }

    @staticmethod
    def _filling_mode(info: Any) -> int:
        filling = int(getattr(info, "filling_mode", 0) or 0)
        if filling & 2:
            return mt5.ORDER_FILLING_IOC
        if filling & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    @staticmethod
    def _minutes_to_timeframe(minutes: int) -> int:
        mapping = {
            1: mt5.TIMEFRAME_M1,
            5: mt5.TIMEFRAME_M5,
            15: mt5.TIMEFRAME_M15,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1,
            240: mt5.TIMEFRAME_H4,
            1440: mt5.TIMEFRAME_D1,
        }
        if minutes not in mapping:
            raise ValueError(
                f"Timeframe {minutes} min não suportado. Use: {sorted(mapping)}"
            )
        return mapping[minutes]

    def _ensure_package(self) -> None:
        if mt5 is None:
            raise MT5UnavailableError(
                "Pacote MetaTrader5 não instalado/suportado nesta plataforma. "
                "No Windows: pip install MetaTrader5 (terminal MT5 aberto)."
            )

    def _require_connected(self) -> None:
        self._ensure_package()
        if not self._connected:
            raise MT5UnavailableError("MT5 não conectado. Chame connect().")


def probe_mt5(cfg: Settings | None = None) -> dict[str, Any]:
    """Health-check sem levantar exceção fatal."""
    cfg = cfg or settings
    payload: dict[str, Any] = {
        "package_available": mt5_package_available(),
        "connected": False,
        "dry_run": cfg.mt5_dry_run,
        "allow_demo_orders": cfg.mt5_allow_demo_orders,
        "can_send_orders": cfg.can_send_mt5_orders(),
        "error": None,
        "account": None,
    }
    if not mt5_package_available():
        payload["error"] = "MetaTrader5 package unavailable"
        return payload
    client = MT5Client(cfg)
    try:
        client.connect()
        payload["connected"] = True
        payload["account"] = client.get_account_info().to_dict()
    except Exception as exc:  # noqa: BLE001 - probe must not crash CLI
        payload["error"] = str(exc)
    finally:
        client.shutdown()
    return payload
