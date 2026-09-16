"""Loop estilo Expert Advisor: conecta, lê dados e aplica estratégia (dry-run)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import NoReturn

from mt5_ea.config import Settings, load_settings
from mt5_ea.connection import MT5Client, MT5ConnectionError
from mt5_ea.strategy import PlaceholderStrategy, Strategy

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_ea(
    settings: Settings,
    *,
    once: bool = False,
    strategy: Strategy | None = None,
) -> int:
    """
    Executa o loop do EA.

    Por padrão `MT5_DRY_RUN=true` — sinais são apenas logados, sem ordens reais.
    """
    strat: Strategy = strategy or PlaceholderStrategy()
    stop = False

    def _handle_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        logger.info("Sinal de interrupção recebido — encerrando após o ciclo atual...")
        stop = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    mode = "DRY-RUN (seguro)" if settings.dry_run else "LIVE (ordens reais habilitadas)"
    logger.info("Modo: %s | símbolo=%s | TF=%smin", mode, settings.symbol, settings.timeframe_minutes)

    try:
        with MT5Client(settings) as client:
            account = client.get_account_info()
            logger.info(
                "Conta %s (%s) | saldo=%.2f %s | equity=%.2f | margem livre=%.2f",
                account.login,
                account.name,
                account.balance,
                account.currency,
                account.equity,
                account.margin_free,
            )

            symbol_info = client.ensure_symbol(settings.symbol)
            logger.info(
                "Símbolo %s | bid=%.5f ask=%.5f | digits=%s | lot min=%.2f",
                symbol_info.name,
                symbol_info.bid,
                symbol_info.ask,
                symbol_info.digits,
                symbol_info.volume_min,
            )

            cycle = 0
            while not stop:
                cycle += 1
                tick = client.get_tick(settings.symbol)
                bars = client.get_rates(settings.symbol)
                last_bar = bars[-1] if bars else None

                logger.info(
                    "[#%s] tick %s | bid=%.5f ask=%.5f last=%.5f @ %s",
                    cycle,
                    tick.symbol,
                    tick.bid,
                    tick.ask,
                    tick.last,
                    tick.time.isoformat(sep=" ", timespec="seconds"),
                )
                if last_bar:
                    logger.info(
                        "[#%s] última barra O=%.5f H=%.5f L=%.5f C=%.5f @ %s",
                        cycle,
                        last_bar["open"],
                        last_bar["high"],
                        last_bar["low"],
                        last_bar["close"],
                        last_bar["time"].isoformat(sep=" ", timespec="seconds"),
                    )

                signal_out = strat.on_tick(tick, bars)
                logger.info(
                    "[#%s] sinal=%s | força=%.3f | %s",
                    cycle,
                    signal_out.action,
                    signal_out.strength,
                    signal_out.reason,
                )

                if signal_out.action in {"buy", "sell"}:
                    # volume mínimo apenas como exemplo; ajuste na sua estratégia
                    client.place_market_order(
                        symbol=settings.symbol,
                        order_type=signal_out.action,
                        volume=symbol_info.volume_min,
                        comment=f"mt5_ea:{signal_out.action}",
                    )

                if once:
                    break

                # sleep em fatias para responder mais rápido ao Ctrl+C
                remaining = float(settings.poll_interval_sec)
                while remaining > 0 and not stop:
                    step = min(0.5, remaining)
                    time.sleep(step)
                    remaining -= step

    except MT5ConnectionError as exc:
        logger.error("%s", exc)
        return 1
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    logger.info("EA finalizado com sucesso.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mt5-ea",
        description="Expert Advisor mínimo em Python para MetaTrader 5 (dry-run por padrão).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa um único ciclo (conta + tick + barras + sinal) e sai.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Sobrescreve MT5_SYMBOL para esta execução.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Desativa dry-run (PERIGOSO: permite envio de ordens reais).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log em nível DEBUG.",
    )
    return parser


def main(argv: list[str] | None = None) -> NoReturn:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    base = load_settings()
    if args.live:
        logger.warning("Modo LIVE ativado via --live. Ordens reais podem ser enviadas.")

    settings = Settings(
        mt5_path=base.mt5_path,
        login=base.login,
        password=base.password,
        server=base.server,
        timeout_ms=base.timeout_ms,
        symbol=(args.symbol or base.symbol).strip().upper(),
        timeframe_minutes=base.timeframe_minutes,
        bars=base.bars,
        poll_interval_sec=base.poll_interval_sec,
        dry_run=False if args.live else base.dry_run,
    )

    code = run_ea(settings, once=args.once)
    sys.exit(code)


if __name__ == "__main__":
    main()
