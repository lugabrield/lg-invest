"""Schemas do Diagnóstico da Carteira (Sprint 11).

Saída do engine de diagnóstico (`engines/portfolio_diagnostics`): uma
lista de insights curtos, explicáveis e baseados em regras simples
(pesos, concentração, composição). Não é IA generativa e não inventa
opinião — cada insight nasce de um limiar documentado em
`engines/portfolio_diagnostics/thresholds.py`.
"""

from __future__ import annotations

from pydantic import BaseModel

# Severidade usada para colorir/ordenar os insights na UI.
SEVERITY_POSITIVE = "positive"  # ponto forte
SEVERITY_INFO = "info"  # observação neutra
SEVERITY_ATTENTION = "attention"  # merece atenção, sem ser grave
SEVERITY_ALERT = "alert"  # concentração/risco relevante


class DiagnosticInsight(BaseModel):
    """Um insight explicável do diagnóstico."""

    code: str  # identificador estável (usado em testes), ex.: "concentration_single_asset"
    severity: str  # positive | info | attention | alert
    title: str
    message: str

    model_config = {"from_attributes": True}


class PortfolioDiagnostics(BaseModel):
    """Resultado consolidado do diagnóstico da carteira."""

    insights: list[DiagnosticInsight]

    model_config = {"from_attributes": True}
