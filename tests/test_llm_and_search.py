from __future__ import annotations

import json

from ia_financeira.config import Settings
from ia_financeira.llm.ollama import extract_json_object, heuristic_decision_json
from ia_financeira.tools.web_search import FinancialWebSearchTool


def test_extract_json_from_fence():
    text = 'Aqui vai:\n```json\n{"acao":"AGUARDAR","confianca":40}\n```\n'
    data = extract_json_object(text)
    assert data["acao"] == "AGUARDAR"
    assert data["confianca"] == 40


def test_heuristic_bullish_context():
    raw = heuristic_decision_json(
        "Notícias indicam balanço acima das expectativas e recomendação de compra. RSI oversold."
    )
    data = json.loads(raw)
    assert data["acao"] in {"COMPRA", "VENDA", "AGUARDAR"}
    assert "confianca" in data


def test_mock_web_search():
    tool = FinancialWebSearchTool(Settings(web_search_backend="mock", web_search_max_results=2))
    items = tool.search("PETR4")
    assert len(items) == 2
    assert "PETR4" in items[0].titulo
