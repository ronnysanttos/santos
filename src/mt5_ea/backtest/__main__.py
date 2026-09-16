"""CLI: python -m mt5_ea.backtest"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, Sequence

from mt5_ea.backtest.data import (
    generate_synthetic_ohlc,
    load_csv,
    load_mt5_history,
)
from mt5_ea.backtest.engine import BacktestConfig, BacktestEngine
from mt5_ea.backtest.metrics import BacktestMetrics
from mt5_ea.config import load_settings
from mt5_ea.risk import RiskParams
from mt5_ea.strategy import DualEmaAtrParams
from mt5_ea.timeframes import parse_timeframe, timeframe_label

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mt5-backtest",
        description="Backtest Dual EMA + ATR (CSV / sintético / histórico real MT5).",
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
        help=(
            "Baixa histórico real via MetaTrader5.copy_rates_* "
            "(requer Windows + terminal MT5 aberto + .env). Não envia ordens."
        ),
    )

    p.add_argument("--symbol", type=str, default=None, help="Símbolo (ex.: EURUSD).")
    p.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Timeframe: M15, H1, D1 ou minutos (ex.: 15). Padrão: .env ou M15.",
    )
    p.add_argument(
        "--bars",
        type=int,
        default=5000,
        help="Qtd. de barras (sintético/MT5 sem --from/--to). Padrão: 5000.",
    )
    p.add_argument(
        "--from",
        dest="date_from",
        type=str,
        default=None,
        help="Início do range MT5 (YYYY-MM-DD ou ISO). Usa copy_rates_range.",
    )
    p.add_argument(
        "--to",
        dest="date_to",
        type=str,
        default=None,
        help="Fim do range MT5 (YYYY-MM-DD ou ISO). Default: agora.",
    )
    p.add_argument("--seed", type=int, default=42, help="Seed do gerador sintético.")
    p.add_argument("--equity", type=float, default=10_000.0, help="Equity inicial.")
    p.add_argument("--spread", type=float, default=10.0, help="Spread em pontos.")
    p.add_argument("--lots", type=float, default=0.10, help="Lote fixo no backtest.")
    p.add_argument("--risk-percent", type=float, default=None, help="Se setado, usa sizing %%.")
    p.add_argument("--ema-fast", type=int, default=None)
    p.add_argument("--ema-slow", type=int, default=None)
    p.add_argument("--atr-period", type=int, default=None)
    p.add_argument("--atr-sl", type=float, default=None)
    p.add_argument("--atr-tp", type=float, default=None)
    p.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Salva relatório completo de métricas em JSON.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--trades",
        action="store_true",
        help="Lista cada trade no relatório.",
    )
    return p


def _parse_cli_datetime(raw: str | None) -> datetime | None:
    if raw is None or raw.strip() == "":
        return None
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"data inválida: {raw!r} (use YYYY-MM-DD ou ISO)")


def _resolve_bars(args: argparse.Namespace):
    settings = None
    try:
        settings = load_settings()
    except Exception as exc:  # noqa: BLE001
        if args.mt5:
            raise SystemExit(f"Falha ao carregar .env para --mt5: {exc}") from exc
        settings = None

    symbol = (args.symbol or (settings.symbol if settings else "EURUSD")).upper()
    default_tf = settings.timeframe_minutes if settings else 15
    tf = parse_timeframe(args.timeframe, default_minutes=default_tf)
    date_from = _parse_cli_datetime(args.date_from)
    date_to = _parse_cli_datetime(args.date_to)

    if args.csv:
        bars = load_csv(args.csv)
        source = f"csv:{args.csv}"
    elif args.mt5:
        if settings is None:
            raise SystemExit(
                "Para --mt5 é necessário um .env válido (copie .env.example). "
                "Requer Windows + terminal MetaTrader 5 aberto. "
                "Este modo só lê histórico — não envia ordens."
            )
        try:
            settings.require_credentials()
        except ValueError as exc:
            raise SystemExit(
                f"{exc}\n"
                "Além disso: Windows + MetaTrader 5 aberto; "
                "pip install MetaTrader5; símbolo no Market Watch."
            ) from exc

        bars = load_mt5_history(
            symbol,
            timeframe_minutes=tf,
            bars=args.bars,
            date_from=date_from,
            date_to=date_to,
            settings=settings.with_overrides(symbol=symbol, dry_run=True),
        )
        if date_from or date_to:
            source = (
                f"mt5:{symbol}:{timeframe_label(tf)}:"
                f"{date_from or '...'}→{date_to or 'now'}"
            )
        else:
            source = f"mt5:{symbol}:{timeframe_label(tf)}:last_{len(bars)}"
    else:
        # padrão / --synthetic
        n_bars = args.bars if args.synthetic or args.bars != 5000 else 500
        bars = generate_synthetic_ohlc(
            bars=n_bars,
            timeframe_minutes=tf,
            seed=args.seed,
        )
        source = f"synthetic:seed={args.seed}"

    return bars, source, symbol, tf, settings


def metrics_to_dict(metrics: BacktestMetrics, *, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": meta,
        "metrics": {
            "initial_equity": metrics.initial_equity,
            "final_equity": metrics.final_equity,
            "net_profit": metrics.net_profit,
            "return_pct": metrics.return_pct,
            "trades": metrics.trades,
            "wins": metrics.wins,
            "losses": metrics.losses,
            "win_rate": metrics.win_rate,
            "profit_factor": (
                None if metrics.profit_factor == float("inf") else metrics.profit_factor
            ),
            "profit_factor_infinite": metrics.profit_factor == float("inf"),
            "max_drawdown": metrics.max_drawdown,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "avg_win": metrics.avg_win,
            "avg_loss": metrics.avg_loss,
            "gross_profit": metrics.gross_profit,
            "gross_loss": metrics.gross_loss,
            "equity_curve_points": len(metrics.equity_curve),
            "equity_min": min(p.equity for p in metrics.equity_curve),
            "equity_max": max(p.equity for p in metrics.equity_curve),
        },
        "trades": [
            {
                "side": t.side,
                "volume": t.volume,
                "entry_time": t.entry_time.isoformat(sep=" "),
                "exit_time": t.exit_time.isoformat(sep=" "),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "pnl": t.pnl,
                "reason_entry": t.reason_entry,
                "reason_exit": t.reason_exit,
            }
            for t in metrics.trade_list
        ],
    }


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    if not args.verbose:
        logging.getLogger("mt5_ea.risk").setLevel(logging.WARNING)

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

    label = timeframe_label(tf)
    print("=" * 60)
    print("Backtest Dual EMA + ATR")
    print(f"Fonte     : {source}")
    print(f"Símbolo   : {symbol} | TF={label} ({tf}m) | barras={len(bars)}")
    if bars:
        print(
            f"Período   : {bars[0].time.isoformat(sep=' ')} → "
            f"{bars[-1].time.isoformat(sep=' ')}"
        )
    print(f"EMA       : {ema_fast}/{ema_slow} | ATR={atr_period} SL×{atr_sl} TP×{atr_tp}")
    print(f"Risco     : {risk.mode} lots={risk.fixed_lots} pct={risk.risk_percent}")
    print("Ordens    : nenhuma (backtest offline / dry-run)")
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

    if args.output_json:
        payload = metrics_to_dict(
            metrics,
            meta={
                "source": source,
                "symbol": symbol,
                "timeframe": label,
                "timeframe_minutes": tf,
                "bars": len(bars),
                "platform": platform.platform(),
                "generated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            },
        )
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"JSON salvo em: {out}")

    return 0


def main(argv: Sequence[str] | None = None) -> NoReturn:
    try:
        code = run_cli(argv)
    except SystemExit as exc:
        # argparse --help etc.; re-raise numeric/None codes as-is
        raise
    except FileNotFoundError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        code = 1
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        code = 2
    except Exception as exc:  # noqa: BLE001
        from mt5_ea.connection import MT5ConnectionError

        if isinstance(exc, MT5ConnectionError):
            print(
                "erro MT5 (histórico): "
                f"{exc}\n"
                "Bloqueadores típicos:\n"
                "  1) SO Linux/macOS — pacote MetaTrader5 só roda no Windows (ou Wine)\n"
                "  2) Terminal MT5 não aberto / não logado\n"
                "  3) .env sem credenciais reais\n"
                "  4) Símbolo ausente no Market Watch\n"
                "Workaround sem terminal: --csv ou --synthetic",
                file=sys.stderr,
            )
            code = 4
        else:
            logger.exception("falha no backtest")
            print(f"erro: {exc}", file=sys.stderr)
            code = 3
    raise SystemExit(code)


if __name__ == "__main__":
    main()
