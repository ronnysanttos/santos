from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from ia_financeira.config import Settings, settings


SYSTEM_PROMPT = """Você é um especialista em gestão de risco e trading quantitativo.
Analise os dados de mercado e as notícias extraídas da web.
Responda APENAS com um JSON válido (sem markdown) contendo:
- acao: COMPRA | VENDA | AGUARDAR
- confianca: número inteiro de 0 a 100
- sentimento: bullish | bearish | neutro
- justificativa: texto curto em português
Não invente fatos que não estejam no contexto."""


@dataclass
class LLMResult:
    text: str
    source: str  # ollama | fallback
    model: str


class OllamaClient:
    """Thin client for Ollama /api/generate."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings

    def is_available(self, timeout: float = 2.0) -> bool:
        try:
            response = requests.get(f"{self.cfg.ollama_url}/api/tags", timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt: str, system: str | None = None) -> LLMResult:
        full_prompt = prompt
        if system:
            full_prompt = f"{system.strip()}\n\n{prompt.strip()}"

        payload = {
            "model": self.cfg.ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": self.cfg.ollama_temperature},
        }
        try:
            response = requests.post(
                f"{self.cfg.ollama_url}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            text = response.json().get("response", "").strip()
            if text:
                return LLMResult(text=text, source="ollama", model=self.cfg.ollama_model)
            raise RuntimeError("Resposta vazia do Ollama")
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            if not self.cfg.ollama_allow_fallback:
                raise RuntimeError(f"Ollama indisponível: {exc}") from exc
            return LLMResult(
                text=heuristic_decision_json(prompt),
                source="fallback",
                model="heuristic-v1",
            )


def heuristic_decision_json(prompt: str) -> str:
    """Deterministic offline decision used when Ollama is down (CI / demo)."""
    lower = prompt.lower()
    bullish_hits = sum(
        1
        for w in (
            "alta",
            "compra",
            "bullish",
            "acima das expectativas",
            "crescimento",
            "otimista",
            "upgrade",
        )
        if w in lower
    )
    bearish_hits = sum(
        1
        for w in (
            "queda",
            "venda",
            "bearish",
            "abaixo das expectativas",
            "recessão",
            "pessimista",
            "downgrade",
            "perda",
        )
        if w in lower
    )
    rsi_oversold = "sobrevendido" in lower or ("rsi" in lower and "28" in lower)
    rsi_overbought = "sobrecomprado" in lower

    if bullish_hits > bearish_hits or rsi_oversold:
        acao, sentimento, conf = "COMPRA", "bullish", 62 + min(20, bullish_hits * 8)
    elif bearish_hits > bullish_hits or rsi_overbought:
        acao, sentimento, conf = "VENDA", "bearish", 62 + min(20, bearish_hits * 8)
    else:
        acao, sentimento, conf = "AGUARDAR", "neutro", 45

    if rsi_oversold and bullish_hits:
        conf = min(85, conf + 10)

    payload = {
        "acao": acao,
        "confianca": int(conf),
        "sentimento": sentimento,
        "justificativa": (
            "Heurística local (Ollama offline): combinação de palavras-chave "
            f"nas notícias/indicadores (bullish={bullish_hits}, bearish={bearish_hits})."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse JSON from model output, tolerating fenced markdown."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("JSON raiz não é objeto")
    return data
