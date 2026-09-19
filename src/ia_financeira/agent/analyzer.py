from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ia_financeira.config import Settings, settings
from ia_financeira.llm.ollama import SYSTEM_PROMPT, OllamaClient, extract_json_object
from ia_financeira.mt5.execution import OrderExecutor, build_order_intent
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
    order: dict[str, Any]
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
            "order": self.order,
            "dry_run": self.decision.get("dry_run", True),
            "steps": self.steps,
        }


class FinancialAnalyzer:
    """ReAct slice: web → MT5/stub indicators → LLM → guardrails → dry-run order."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self.search = FinancialWebSearchTool(self.cfg)
        self.market = MarketDataProvider(self.cfg)
        self.llm = OllamaClient(self.cfg)
        self.risk = RiskGuardrails(self.cfg)
        self.executor = OrderExecutor(self.cfg)

    def analyze(self, ticker: str) -> AnalysisResult:
        steps: list[str] = []
        symbol = ticker.upper().strip()

        steps.append(f"1. Identificar ativo: {symbol}")
        news = self.search.search(symbol)
        steps.append(f"2. Busca web: {len(news)} notícia(s)")

        snap = self.market.snapshot(symbol)
        steps.append(
            f"3. Snapshot de mercado ({snap.mode}) "
            f"RSI={snap.rsi_14} MA200={snap.ma_200} ATR={snap.atr_14}"
        )

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
        steps.append("4. Consultar LLM local (Ollama / qwen2.5:7b)")
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
            + ("ordem elegível" if verdict.allowed else "bloqueado / aguardar")
        )
        if verdict.reasons:
            steps.append("   motivos: " + "; ".join(verdict.reasons))

        intent = None
        if verdict.allowed:
            intent = build_order_intent(
                action=verdict.action,
                snapshot=snap,
                confidence=verdict.confidence,
                cfg=self.cfg,
            )
        order_result = self.executor.execute(intent)
        steps.append(
            f"7. Execução: {order_result.get('status')} "
            f"(dry_run={self.cfg.mt5_dry_run}, "
            f"allow_demo={self.cfg.mt5_allow_demo_orders})"
        )

        effective = dict(decision)
        effective["acao"] = verdict.action
        effective["ordem_permitida"] = verdict.allowed
        effective["dry_run"] = not self.cfg.can_send_mt5_orders()

        return AnalysisResult(
            ticker=symbol,
            decision=effective,
            llm_source=llm_result.source,
            llm_model=llm_result.model,
            news=news,
            market=snap,
            guardrails=verdict,
            order=order_result,
            raw_llm=llm_result.text,
            context=context,
            steps=steps,
        )
