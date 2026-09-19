from __future__ import annotations

from ia_financeira.config import Settings
from ia_financeira.risk.guardrails import RiskGuardrails


def test_blocks_low_confidence_buy():
    g = RiskGuardrails(Settings(min_confidence=70))
    verdict = g.evaluate({"acao": "COMPRA", "confianca": 55})
    assert verdict.allowed is False
    assert verdict.action == "AGUARDAR"
    assert any("confiança" in r.lower() or "confian" in r.lower() for r in verdict.reasons)


def test_allows_high_confidence_buy():
    g = RiskGuardrails(Settings(min_confidence=70))
    verdict = g.evaluate({"acao": "COMPRA", "confianca": 80})
    assert verdict.allowed is True
    assert verdict.action == "COMPRA"


def test_daily_loss_blocks_entries():
    g = RiskGuardrails(Settings(min_confidence=70, daily_loss_limit_brl=300))
    g.record_daily_loss(300)
    verdict = g.evaluate({"acao": "VENDA", "confianca": 90})
    assert verdict.allowed is False
    assert verdict.action == "AGUARDAR"


def test_high_impact_window_blocks():
    g = RiskGuardrails(Settings(min_confidence=70))
    g.set_high_impact_window(True)
    verdict = g.evaluate({"acao": "COMPRA", "confianca": 95})
    assert verdict.allowed is False
