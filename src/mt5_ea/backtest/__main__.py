"""CLI: python -m mt5_ea.backtest"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from mt5_ea.backtest.data import (
    generate_synthetic_ohlc,
    load_csv,
    load_mt5_history,
)
from mt5_ea.backtest.engine import BacktestConfig, BacktestEngine
from mt5_ea.config import load_settings
from mt5_ea.risk import RiskParams
from mt5_ea.strategy import DualEmaAtrParams

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mt5-backtest",
        description="Backtest offline Dual EMA + ATR (CSV / sintético / MT5 opcional).",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Caminho para CSV OHLC (time,open,high,low,close[,volume]).",
    )
    src.add_argument(
        "--synthetic",
        action="store_true",
        help="Usa série OHLC sintética determinística (padrão se nada for informado).",
    )
    src.add_argument(
        "--mt5",
        action="store_true",
        help="Baixa histórico do terminal MetaTrader 5 (requer Windows/Wine + .env).",
    )

    p.add_argument("--symbol", type=str, default=None, help="Símbolo (MT5 / relatório).")
    p.add_argument("--timeframe", type=int, default=None, help="Timeframe em minutos.")
    p.add_argument("--bars", type=int, default=500, help="Qtd. de barras (sintético/MT5).")
    p.add_argument("--seed", type=int, default=42, help="Seed do gerador sintético.")
    p.add_argument("--equity", type=float, default=10_000.0, help="Equity inicial.")
    p.add_argument("--spread", type=float, default=10.0, help="Spread em pontos.")
    p.add_argument("--lots", type=float, default=0.10, help="Lote fixo no backtest.")
    p.add_argument("--risk-percent", type=float, default=None, help="Se setado, usa sizing %.")
    p.add_argument("--ema-fast", type=int, default=None)
    p.add_argument("--ema-slow", type=int, default=None)
    p.add_argument("--atr-period", type=int, default=None)
    p.add_argument("--atr-sl", type=float, default=None)
    p.add_argument("--atr-tp", type=float, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--trades",
        action="store_true",
        help="Lista cada trade no relatório.",
    )
    return p


def _resolve_bars(args: argparse.Namespace):
    settings = None
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001 — backtest offline não exige .env válido
        settings = None

    symbol = (args.symbol or (settings.symbol if settings else "EURUSD")).upper()
    tf = args.timeframe or (settings.timeframe_minutes if settings else 15)

    if args.csv:
        bars = load_csv(args.csv)
        source = f"csv:{args.csv}"
    elif args.mt5:
        if settings is None:
            raise SystemExit("Para --mt5 é necessário um .env válido com credenciais.")
        bars = load_mt5_history(
            symbol,
            timeframe_minutes=tf,
            bars=args.bars,
            settings=settings.with_overrides(symbol=symbol),
        )
        source = f"mt5:{symbol}:{tf}m"
    else:
        # padrão: sintético (também se --synthetic)
        bars = generate_synthetic_ohlc(
            bars=args.bars,
            timeframe_minutes=tf,
            seed=args.seed,
        )
        source = f"synthetic:seed={args.seed}"

    return bars, source, symbol, tf, settings


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    bars, source, symbol, tf, settings = _resolve_bars(args)

    ema_fast = args.ema_fast or (settings.ema_fast if settings else 12)
    ema_slow = args.ema_slow or (settings.ema_slow if settings else 26)
    atr_period = args.atr_period or (settings.atr_period if settings else 14)
    atr_sl = args.atr_sl or (settings.atr_sl_mult if settings else 1.5)
    atr_tp = args.atr_tp or (settings.atr_tp_mult if settings else 2.5)

    if args.risk_percent is not None:
        risk = RiskParams(
            mode="percent",
            risk_percent=args.risk_percent,
            max_positions=1,
            max_daily_loss_percent=0.0,
            max_spread_points=0.0,
            session_start_hour=None,
            session_end_hour=None,
        )
    else:
        risk = RiskParams(
            mode="fixed",
            fixed_lots=args.lots,
            max_positions=1,
            max_daily_loss_percent=0.0,
            max_spread_points=0.0,
            session_start_hour=None,
            session_end_hour=None,
        )

    engine = BacktestEngine(
        BacktestConfig(
            initial_equity=args.equity,
            spread_points=args.spread,
            strategy_params=DualEmaAtrParams(
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                atr_period=atr_period,
                atr_sl_mult=atr_sl,
                atr_tp_mult=atr_tp,
            ),
            risk_params=risk,
        )
    )

    print("=" * 60)
    print("Backtest Dual EMA + ATR")
    print(f"Fonte     : {source}")
    print(f"Símbolo   : {symbol} | TF={tf}m | barras={len(bars)}")
    print(f"EMA       : {ema_fast}/{ema_slow} | ATR={atr_period} SL×{atr_sl} TP×{atr_tp}")
    print(f"Risco     : {risk.mode} lots={risk.fixed_lots} pct={risk.risk_percent}")
    print("=" * 60)

    metrics = engine.run(bars)
    for line in metrics.summary_lines():
        print(line)

    if args.trades and metrics.trade_list:
        print("-" * 60)
        print("Trades:")
        for i, t in enumerate(metrics.trade_list, 1):
            print(
                f"  #{i:02d} {t.side:4s} vol={t.volume:.2f} "
                f"entry={t.entry_price:.5f} exit={t.exit_price:.5f} "
                f"pnl={t.pnl:+.2f} | {t.reason_exit}"
            )

    # equity curve summary
    eq = metrics.equity_curve
    if len(eq) >= 2:
        print("-" * 60)
        print(
            f"Curva equity: início={eq[0].equity:.2f} "
            f"mín={min(p.equity for p in eq):.2f} "
            f"máx={max(p.equity for p in eq):.2f} "
            f"fim={eq[-1].equity:.2f} "
            f"({len(eq)} pontos)"
        )

    return 0


def main(argv: Sequence[str] | None = None) -> NoReturn:
    try:
        code = run_cli(argv)
    except FileNotFoundError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        code = 1
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        code = 2
    except Exception as exc:  # noqa: BLE001
        logger.exception("falha no backtest")
        print(f"erro: {exc}", file=sys.stderr)
        code = 3
    raise SystemExit(code)


if __name__ == "__main__":
    main()
