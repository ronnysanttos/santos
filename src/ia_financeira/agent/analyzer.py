from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ia_financeira.config import Settings, settings
from ia_financeira.llm.ollama import SYSTEM_PROMPT, OllamaClient, extract_json_object
from ia_financeira.risk.guardrails import GuardrailVerdict, RiskGuardrails
from ia_financeira.tools.market_data import MarketDataProvider, MarketSnapshot
from ia_financeira.tools.web_search import FinancialWebSearchTool, NewsItem


@dataclass
class AnalysisResult:
    ticker: str
    decision: dict[str, Any]
    llm_source: str
    llm_model: str
    news: list[NewsItem]
    market: MarketSnapshot
    guardrails: GuardrailVerdict
    raw_llm: str
    context: str
    steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "decision": self.decision,
            "llm": {"source": self.llm_source, "model": self.llm_model},
            "news": [n.to_dict() for n in self.news],
            "market": self.market.to_dict(),
            "guardrails": self.guardrails.to_dict(),
            "dry_run": True,
            "steps": self.steps,
        }


class FinancialAnalyzer:
    """Vertical slice ReAct: web → market stub → LLM → guardrails."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self.search = FinancialWebSearchTool(self.cfg)
        self.market = MarketDataProvider(self.cfg)
        self.llm = OllamaClient(self.cfg)
        self.risk = RiskGuardrails(self.cfg)

    def analyze(self, ticker: str) -> AnalysisResult:
        steps: list[str] = []
        symbol = ticker.upper().strip()

        steps.append(f"1. Identificar ativo: {symbol}")
        news = self.search.search(symbol)
        steps.append(f"2. Busca web: {len(news)} notícia(s)")

        snap = self.market.snapshot(symbol)
        steps.append(f"3. Snapshot de mercado ({snap.mode})")

        news_block = json.dumps([n.to_dict() for n in news], ensure_ascii=False, indent=2)
        context = (
            f"{snap.as_context_block()}\n"
            f"[BUSCA WEB]:\n{news_block}"
        )
        prompt = (
            f"Contexto Atual:\n{context}\n\n"
            "Decisão (COMPRA/VENDA/AGUARDAR) em JSON com "
            "acao, confianca, sentimento, justificativa:"
        )
        steps.append("4. Consultar LLM local (Ollama)")
        llm_result = self.llm.generate(prompt, system=SYSTEM_PROMPT)
        steps.append(f"5. Resposta LLM via {llm_result.source} ({llm_result.model})")

        try:
            decision = extract_json_object(llm_result.text)
        except (json.JSONDecodeError, ValueError):
            decision = {
                "acao": "AGUARDAR",
                "confianca": 0,
                "sentimento": "neutro",
                "justificativa": "Falha ao parsear JSON do modelo; operação suspensa.",
            }
            steps.append("6. Parse JSON falhou — forçando AGUARDAR")

        # Normalize keys
        decision["acao"] = str(decision.get("acao", "AGUARDAR")).upper()
        try:
            decision["confianca"] = int(decision.get("confianca", 0))
        except (TypeError, ValueError):
            decision["confianca"] = 0
        decision.setdefault("sentimento", "neutro")
        decision.setdefault("justificativa", "")

        verdict = self.risk.evaluate(decision)
        steps.append(
            "6. Guardrails: "
            + ("ordem permitida (dry-run)" if verdict.allowed else "bloqueado / aguardar")
        )
        if verdict.reasons:
            steps.append("   motivos: " + "; ".join(verdict.reasons))

        # Effective decision after guardrails
        effective = dict(decision)
        effective["acao"] = verdict.action
        effective["ordem_permitida"] = verdict.allowed
        effective["dry_run"] = self.cfg.mt5_dry_run

        return AnalysisResult(
            ticker=symbol,
            decision=effective,
            llm_source=llm_result.source,
            llm_model=llm_result.model,
            news=news,
            market=snap,
            guardrails=verdict,
            raw_llm=llm_result.text,
            context=context,
            steps=steps,
        )
