"""Loop estilo Expert Advisor: estratégia → risco → execução (dry-run padrão)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from typing import NoReturn

from mt5_ea.config import Settings, load_settings
from mt5_ea.connection import MT5Client, MT5ConnectionError
from mt5_ea.execution import ExecutionEngine
from mt5_ea.risk import ContractSpec, RiskContext, RiskManager, RiskParams
from mt5_ea.strategy import DualEmaAtrParams, DualEmaAtrStrategy, Strategy

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_strategy(settings: Settings) -> DualEmaAtrStrategy:
    return DualEmaAtrStrategy(
        DualEmaAtrParams(
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            atr_period=settings.atr_period,
            atr_sl_mult=settings.atr_sl_mult,
            atr_tp_mult=settings.atr_tp_mult,
        )
    )


def _build_risk(settings: Settings) -> RiskManager:
    return RiskManager(
        RiskParams(
            mode=settings.risk_mode,
            risk_percent=settings.risk_percent,
            fixed_lots=settings.fixed_lots,
            max_positions=settings.max_positions,
            max_daily_loss_percent=settings.max_daily_loss_percent,
            max_spread_points=settings.max_spread_points,
            session_start_hour=settings.session_start_hour,
            session_end_hour=settings.session_end_hour,
            magic=settings.magic,
        )
    )


def run_ea(
    settings: Settings,
    *,
    once: bool = False,
    strategy: Strategy | None = None,
) -> int:
    """
    Executa o loop do EA.

    Fluxo: dados → sinal (estratégia) → decisão (risco) → execução.
    Por padrão `MT5_DRY_RUN=true` — ordens não são enviadas.
    """
    strat: Strategy = strategy or _build_strategy(settings)
    risk = _build_risk(settings)
    stop = False

    def _handle_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        logger.info("Sinal de interrupção recebido — encerrando após o ciclo atual...")
        stop = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    mode = "DRY-RUN (seguro)" if settings.dry_run else "LIVE (ordens reais habilitadas)"
    logger.info(
        "Modo: %s | símbolo=%s | TF=%smin | EMA %s/%s | ATR=%s | risco=%s",
        mode,
        settings.symbol,
        settings.timeframe_minutes,
        settings.ema_fast,
        settings.ema_slow,
        settings.atr_period,
        settings.risk_mode,
    )

    try:
        with MT5Client(settings) as client:
            executor = ExecutionEngine(
                client,
                magic=settings.magic,
                dry_run=settings.dry_run,
            )

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
                "Símbolo %s | bid=%.5f ask=%.5f | digits=%s | lot min=%.2f step=%.2f",
                symbol_info.name,
                symbol_info.bid,
                symbol_info.ask,
                symbol_info.digits,
                symbol_info.volume_min,
                symbol_info.volume_step,
            )

            cycle = 0
            while not stop:
                cycle += 1
                tick = client.get_tick(settings.symbol)
                bars = client.get_rates(settings.symbol)
                account = client.get_account_info()
                positions = client.get_positions(
                    symbol=settings.symbol,
                    magic=settings.magic,
                )
                daily_pnl = client.get_daily_realized_pnl(magic=settings.magic)

                open_side = positions[0].side if positions else None
                last_bar = bars[-1] if bars else None

                logger.info(
                    "[#%s] tick %s | bid=%.5f ask=%.5f | pos=%s side=%s | daily_pnl=%.2f",
                    cycle,
                    tick.symbol,
                    tick.bid,
                    tick.ask,
                    len(positions),
                    open_side or "-",
                    daily_pnl,
                )
                if last_bar:
                    logger.debug(
                        "[#%s] última barra O=%.5f H=%.5f L=%.5f C=%.5f @ %s",
                        cycle,
                        last_bar["open"],
                        last_bar["high"],
                        last_bar["low"],
                        last_bar["close"],
                        last_bar["time"].isoformat(sep=" ", timespec="seconds"),
                    )

                signal_out = strat.evaluate(tick, bars, open_side=open_side)
                logger.info(
                    "[#%s] SINAL %s | força=%.3f | %s",
                    cycle,
                    signal_out.action,
                    signal_out.strength,
                    signal_out.reason,
                )

                symbol_info = client.ensure_symbol(settings.symbol)
                ctx = RiskContext(
                    equity=account.equity,
                    balance=account.balance,
                    bid=tick.bid,
                    ask=tick.ask,
                    open_positions=len(positions),
                    open_side=open_side,
                    daily_pnl=daily_pnl,
                    now=datetime.now(),
                    contract=ContractSpec(
                        point=symbol_info.point,
                        digits=symbol_info.digits,
                        volume_min=symbol_info.volume_min,
                        volume_max=symbol_info.volume_max,
                        volume_step=symbol_info.volume_step,
                        tick_size=symbol_info.trade_tick_size,
                        tick_value=symbol_info.trade_tick_value,
                    ),
                )

                decision = risk.decide(signal_out, ctx)
                logger.info(
                    "[#%s] DECISÃO %s | vol=%s | %s",
                    cycle,
                    decision.action,
                    f"{decision.volume:.2f}" if decision.volume is not None else "-",
                    decision.reason,
                )

                exec_result = executor.execute(decision, symbol=settings.symbol)
                logger.info("[#%s] EXEC resultado=%s", cycle, exec_result.get("status"))

                if once:
                    break

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
        description=(
            "EA Python MT5: Dual EMA + ATR com gestão de risco "
            "(dry-run por padrão)."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa um único ciclo e sai.",
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

    settings = base.with_overrides(
        symbol=args.symbol,
        dry_run=False if args.live else None,
    )

    code = run_ea(settings, once=args.once)
    sys.exit(code)


if __name__ == "__main__":
    main()
