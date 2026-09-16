"""Módulo de conexão com o terminal MetaTrader 5."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    volume_step: float
    trade_tick_size: float
    trade_tick_value: float


@dataclass(frozen=True, slots=True)
class TickSnapshot:
    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float
    volume: int


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    ticket: int
    symbol: str
    side: str  # buy | sell
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    magic: int
    comment: str


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

        tick_size = float(info.trade_tick_size) or float(info.point)
        tick_value = float(info.trade_tick_value)
        if tick_value <= 0:
            # fallback conservador para brokers que reportam 0
            tick_value = float(info.point)

        return SymbolSnapshot(
            name=name,
            bid=float(tick.bid),
            ask=float(tick.ask),
            point=float(info.point),
            digits=int(info.digits),
            trade_mode=int(info.trade_mode),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
            volume_step=float(info.volume_step) or float(info.volume_min) or 0.01,
            trade_tick_size=tick_size,
            trade_tick_value=tick_value,
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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retorna barras OHLC via MetaTrader5.copy_rates_*.

        - Com `date_from`/`date_to`: usa `copy_rates_range`
        - Caso contrário: `copy_rates_from_pos` com as últimas `count` barras
        """
        self._require_connected()
        name = (symbol or self._settings.symbol).upper()
        minutes = timeframe_minutes or self._settings.timeframe_minutes
        tf = self._minutes_to_timeframe(minutes)

        if not mt5.symbol_select(name, True):
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Falha ao selecionar símbolo {name}: ({code}) {message}"
            )

        if date_from is not None or date_to is not None:
            start = date_from or (datetime.now() - timedelta(days=365))
            end = date_to or datetime.now()
            if end <= start:
                raise ValueError("date_to deve ser posterior a date_from")
            rates = mt5.copy_rates_range(name, tf, start, end)
            api = "copy_rates_range"
        else:
            bars = count or self._settings.bars
            if bars < 1:
                raise ValueError("count de barras deve ser >= 1")
            rates = mt5.copy_rates_from_pos(name, tf, 0, bars)
            api = "copy_rates_from_pos"

        if rates is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(
                f"Falha em {api} para {name} TF={minutes}m: ({code}) {message}"
            )
        if len(rates) == 0:
            raise MT5ConnectionError(
                f"{api} retornou 0 barras para {name} TF={minutes}m"
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

    def get_positions(
        self,
        *,
        symbol: str | None = None,
        magic: int | None = None,
    ) -> list[PositionSnapshot]:
        self._require_connected()
        name = (symbol or self._settings.symbol).upper()
        positions = mt5.positions_get(symbol=name)
        if positions is None:
            return []

        magic_filter = self._settings.magic if magic is None else magic
        out: list[PositionSnapshot] = []
        for pos in positions:
            if magic_filter is not None and int(pos.magic) != int(magic_filter):
                continue
            side = "buy" if int(pos.type) == mt5.POSITION_TYPE_BUY else "sell"
            out.append(
                PositionSnapshot(
                    ticket=int(pos.ticket),
                    symbol=str(pos.symbol),
                    side=side,
                    volume=float(pos.volume),
                    price_open=float(pos.price_open),
                    sl=float(pos.sl),
                    tp=float(pos.tp),
                    profit=float(pos.profit),
                    magic=int(pos.magic),
                    comment=str(pos.comment),
                )
            )
        return out

    def get_daily_realized_pnl(self, *, magic: int | None = None) -> float:
        """Soma profit+swap+commission dos deals de saída desde 00:00 local."""
        self._require_connected()
        magic_filter = self._settings.magic if magic is None else magic
        now = datetime.now()
        day_start = datetime(now.year, now.month, now.day)
        deals = mt5.history_deals_get(day_start, now + timedelta(seconds=1))
        if deals is None:
            return 0.0

        total = 0.0
        for deal in deals:
            if magic_filter is not None and int(deal.magic) != int(magic_filter):
                continue
            # DEAL_ENTRY_OUT=1, DEAL_ENTRY_INOUT=2 (constantes oficiais MT5)
            entry = int(getattr(deal, "entry", -1))
            entry_out = int(getattr(mt5, "DEAL_ENTRY_OUT", 1))
            entry_inout = int(getattr(mt5, "DEAL_ENTRY_INOUT", 2))
            if entry not in (entry_out, entry_inout):
                continue
            total += float(deal.profit) + float(deal.swap) + float(deal.commission)
        return total

    def place_market_order(
        self,
        *,
        symbol: str,
        order_type: str,
        volume: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        magic: int | None = None,
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

        magic_id = self._settings.magic if magic is None else magic

        if self._settings.dry_run:
            logger.warning(
                "[DRY-RUN] Ordem NÃO enviada: %s %.2f %s SL=%s TP=%s (%s)",
                side.upper(),
                volume,
                symbol,
                stop_loss,
                take_profit,
                comment,
            )
            return {
                "status": "dry_run",
                "dry_run": True,
                "retcode": None,
                "symbol": symbol,
                "side": side,
                "volume": volume,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "magic": magic_id,
                "comment": comment,
            }

        tick = self.get_tick(symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            raise MT5ConnectionError(f"symbol_info indisponível para {symbol}")

        order_type_const = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "buy" else tick.bid
        digits = int(info.digits)

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type_const,
            "price": price,
            "deviation": 20,
            "magic": int(magic_id),
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }
        if stop_loss is not None:
            request["sl"] = round(float(stop_loss), digits)
        if take_profit is not None:
            request["tp"] = round(float(take_profit), digits)

        result = mt5.order_send(request)
        if result is None:
            code, message = mt5.last_error()
            raise MT5ConnectionError(f"order_send falhou: ({code}) {message}")

        payload = {
            "status": "sent",
            "dry_run": False,
            "retcode": int(result.retcode),
            "deal": int(getattr(result, "deal", 0) or 0),
            "order": int(getattr(result, "order", 0) or 0),
            "volume": float(getattr(result, "volume", volume) or volume),
            "price": float(getattr(result, "price", price) or price),
            "comment": str(getattr(result, "comment", comment) or comment),
            "symbol": symbol,
            "side": side,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "magic": magic_id,
        }
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("Ordem rejeitada: %s", payload)
        else:
            logger.info("Ordem executada: %s", payload)
        return payload

    def close_positions(
        self,
        *,
        symbol: str,
        side: str | None = None,
        magic: int | None = None,
    ) -> dict[str, Any]:
        """Fecha posições do símbolo/magic (filtra por lado se informado)."""
        self._require_connected()
        positions = self.get_positions(symbol=symbol, magic=magic)
        if side is not None:
            side_norm = side.strip().lower()
            positions = [p for p in positions if p.side == side_norm]

        if not positions:
            logger.info("Nenhuma posição para fechar (%s side=%s)", symbol, side)
            return {"status": "noop", "closed": 0, "dry_run": self._settings.dry_run}

        if self._settings.dry_run:
            tickets = [p.ticket for p in positions]
            logger.warning("[DRY-RUN] Fechamento NÃO enviado: tickets=%s", tickets)
            return {
                "status": "dry_run",
                "dry_run": True,
                "closed": 0,
                "would_close": tickets,
            }

        closed = 0
        results: list[dict[str, Any]] = []
        for pos in positions:
            close_side = "sell" if pos.side == "buy" else "buy"
            tick = self.get_tick(symbol)
            price = tick.bid if close_side == "sell" else tick.ask
            info = mt5.symbol_info(symbol)
            order_type = (
                mt5.ORDER_TYPE_SELL if close_side == "sell" else mt5.ORDER_TYPE_BUY
            )
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(pos.volume),
                "type": order_type,
                "position": int(pos.ticket),
                "price": price,
                "deviation": 20,
                "magic": int(pos.magic),
                "comment": "mt5_ea:exit",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._filling_mode(info) if info else mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None:
                code, message = mt5.last_error()
                results.append({"ticket": pos.ticket, "error": f"({code}) {message}"})
                continue
            ok = int(result.retcode) == mt5.TRADE_RETCODE_DONE
            if ok:
                closed += 1
            results.append(
                {
                    "ticket": pos.ticket,
                    "retcode": int(result.retcode),
                    "ok": ok,
                }
            )

        return {
            "status": "sent",
            "dry_run": False,
            "closed": closed,
            "results": results,
        }

    @staticmethod
    def _filling_mode(info: Any) -> int:
        filling = int(getattr(info, "filling_mode", 0) or 0)
        # Prefer IOC, depois FOK, depois RETURN
        if filling & 2:  # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        if filling & 1:  # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

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
