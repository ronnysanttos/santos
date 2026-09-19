from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from ia_financeira.config import Settings, settings


@dataclass
class NewsItem:
    titulo: str
    resumo: str
    link: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class FinancialWebSearchTool:
    """Ferramenta que permite ao LLM pesquisar notícias financeiras atualizadas."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings

    def buscar_noticias_ativo(self, ticker: str, max_resultados: int | None = None) -> str:
        limit = max_resultados or self.cfg.web_search_max_results
        items = self.search(ticker, max_results=limit)
        return json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2)

    def search(self, ticker: str, max_results: int | None = None) -> list[NewsItem]:
        limit = max_results or self.cfg.web_search_max_results
        backend = self.cfg.web_search_backend
        if backend == "mock":
            return self._mock_results(ticker, limit)
        try:
            return self._duckduckgo(ticker, limit)
        except Exception:
            # Network / rate-limit resilience for demos and CI
            return self._mock_results(ticker, limit)

    def _duckduckgo(self, ticker: str, max_results: int) -> list[NewsItem]:
        try:
            from ddgs import DDGS
        except ImportError:  # pragma: no cover - legacy package name
            from duckduckgo_search import DDGS

        query = f"noticias mercado financeiro {ticker} hoje analise"
        with DDGS() as ddgs:
            raw: list[dict[str, Any]] = list(ddgs.text(query, max_results=max_results))
        items: list[NewsItem] = []
        for item in raw:
            items.append(
                NewsItem(
                    titulo=str(item.get("title") or ""),
                    resumo=str(item.get("body") or ""),
                    link=str(item.get("href") or ""),
                )
            )
        if not items:
            return self._mock_results(ticker, max_results)
        return items

    def _mock_results(self, ticker: str, max_results: int) -> list[NewsItem]:
        samples = [
            NewsItem(
                titulo=f"{ticker}: analistas veem balanço acima das expectativas",
                resumo=(
                    f"Relatórios recentes apontam resultados corporativos de {ticker} "
                    "acima das expectativas e recomendação de compra por casas locais."
                ),
                link=f"https://example.local/news/{ticker.lower()}-bullish",
            ),
            NewsItem(
                titulo=f"Macro: mercado monitora Copom e impacto em {ticker}",
                resumo=(
                    "Expectativa de juros e inflação segue no radar; tom misto "
                    "para ativos de risco no curto prazo."
                ),
                link=f"https://example.local/macro/{ticker.lower()}",
            ),
            NewsItem(
                titulo=f"{ticker} opera em consolidação após volatilidade",
                resumo=(
                    "Fluxo estrangeiro e commodity correlatas influenciam o papel; "
                    "cenário tático neutro até novos catalisadores."
                ),
                link=f"https://example.local/tech/{ticker.lower()}",
            ),
        ]
        return samples[:max_results]
