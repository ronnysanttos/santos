from __future__ import annotations

from ia_financeira.agent.analyzer import FinancialAnalyzer
from ia_financeira.config import Settings


def test_analyze_vertical_slice_with_mocks():
    cfg = Settings(
        web_search_backend="mock",
        ollama_allow_fallback=True,
        market_data_mode="stub",
        min_confidence=70,
        mt5_dry_run=True,
    )
    result = FinancialAnalyzer(cfg).analyze("PETR4")
    assert result.ticker == "PETR4"
    assert result.llm_source in {"ollama", "fallback"}
    assert result.decision["acao"] in {"COMPRA", "VENDA", "AGUARDAR"}
    assert "ordem_permitida" in result.decision
    assert len(result.news) >= 1
    assert result.market.mode == "stub"
    assert any("Identificar ativo" in s for s in result.steps)
