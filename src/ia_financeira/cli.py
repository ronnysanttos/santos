from __future__ import annotations

import argparse
import json
import sys

from ia_financeira import __version__
from ia_financeira.agent.analyzer import FinancialAnalyzer
from ia_financeira.config import settings
from ia_financeira.llm.ollama import OllamaClient
from ia_financeira.mt5.client import probe_mt5
from ia_financeira.tools.web_search import FinancialWebSearchTool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ia-financeira",
        description="IA Financeira Local (Ollama qwen2.5:7b + DuckDuckGo + MT5 dry-run)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser(
        "analyze",
        help="Web + indicadores (MT5/stub) + LLM + guardrails + dry-run order",
    )
    analyze.add_argument("ticker", nargs="?", default=settings.default_ticker)
    analyze.add_argument("--pretty", action="store_true", help="JSON indentado")

    search = sub.add_parser("search", help="Somente busca de notícias do ativo")
    search.add_argument("ticker", nargs="?", default=settings.default_ticker)
    search.add_argument("--pretty", action="store_true")

    sub.add_parser("health", help="Checa Ollama, busca e MT5")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        client = OllamaClient()
        ok = client.is_available()
        mt5_info = probe_mt5()
        payload = {
            "ollama_url": settings.ollama_url,
            "ollama_model": settings.ollama_model,
            "ollama_available": ok,
            "fallback_enabled": settings.ollama_allow_fallback,
            "web_search_backend": settings.web_search_backend,
            "min_confidence": settings.min_confidence,
            "daily_loss_limit_brl": settings.daily_loss_limit_brl,
            "market_data_mode": settings.market_data_mode,
            "mt5": mt5_info,
            "mt5_dry_run": settings.mt5_dry_run,
            "mt5_allow_demo_orders": settings.mt5_allow_demo_orders,
            "can_send_mt5_orders": settings.can_send_mt5_orders(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok or settings.ollama_allow_fallback else 1

    if args.command == "search":
        tool = FinancialWebSearchTool()
        raw = tool.buscar_noticias_ativo(args.ticker)
        if args.pretty:
            print(raw)
        else:
            print(json.dumps(json.loads(raw), ensure_ascii=False))
        return 0

    if args.command == "analyze":
        result = FinancialAnalyzer().analyze(args.ticker)
        data = result.to_dict()
        print("=== PASSOS DO AGENTE ===", file=sys.stderr)
        for step in result.steps:
            print(step, file=sys.stderr)
        print("=== DECISÃO / ORDEM ===", file=sys.stderr)
        indent = 2 if args.pretty else None
        print(json.dumps(data, ensure_ascii=False, indent=indent))
        return 0

    parser.error(f"comando desconhecido: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
