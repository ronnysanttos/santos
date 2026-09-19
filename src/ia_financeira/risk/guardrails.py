from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ia_financeira.config import Settings, settings


ALLOWED_ACTIONS = {"COMPRA", "VENDA", "AGUARDAR"}


@dataclass
class GuardrailVerdict:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    action: str = "AGUARDAR"
    confidence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "action": self.action,
            "confidence": self.confidence,
        }


class RiskGuardrails:
    """Travas críticas do protocolo de segurança (PDF §7)."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._daily_loss_brl: float = 0.0
        self._loss_day: date | None = None
        self._high_impact_active: bool = False

    def record_daily_loss(self, loss_brl: float, on_day: date | None = None) -> None:
        day = on_day or date.today()
        if self._loss_day != day:
            self._loss_day = day
            self._daily_loss_brl = 0.0
        self._daily_loss_brl += max(0.0, loss_brl)

    def set_high_impact_window(self, active: bool) -> None:
        self._high_impact_active = active

    def evaluate(self, decision: dict[str, Any]) -> GuardrailVerdict:
        reasons: list[str] = []
        action = str(decision.get("acao", "AGUARDAR")).upper().strip()
        if action not in ALLOWED_ACTIONS:
            reasons.append(f"acao inválida: {action}")
            action = "AGUARDAR"

        try:
            confidence = int(decision.get("confianca", 0))
        except (TypeError, ValueError):
            confidence = 0
            reasons.append("confianca inválida")

        if action in {"COMPRA", "VENDA"} and confidence < self.cfg.min_confidence:
            reasons.append(
                f"confiança {confidence}% abaixo do mínimo {self.cfg.min_confidence}%"
            )

        if self._daily_loss_brl >= self.cfg.daily_loss_limit_brl:
            reasons.append(
                f"limite de perda diária atingido "
                f"(R$ {self._daily_loss_brl:.2f} >= R$ {self.cfg.daily_loss_limit_brl:.2f})"
            )

        if self._high_impact_active:
            reasons.append(
                f"janela de notícia de alto impacto (±{self.cfg.high_impact_pause_minutes} min)"
            )

        # Bloqueia envio de ordem se qualquer trava disparar.
        if action in {"COMPRA", "VENDA"} and reasons:
            final_action = "AGUARDAR"
            allowed = False
        elif action in {"COMPRA", "VENDA"}:
            final_action = action
            allowed = True
        else:
            final_action = "AGUARDAR"
            allowed = False

        return GuardrailVerdict(
            allowed=allowed,
            reasons=reasons,
            action=final_action,
            confidence=confidence,
        )
