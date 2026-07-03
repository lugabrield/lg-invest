"""Schema de saída do Valuation Engine v1 (Sprint 15 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

VALUATION_CLASSIFICATIONS = ("barato", "neutro", "caro", "indeterminado")


class MetricVerdict(BaseModel):
    """Veredito de um múltiplo individual (ex.: P/L = 'barato')."""

    field: str
    label: str
    value: Decimal | None = None
    verdict: str  # "barato" | "neutro" | "caro" | "indeterminado"
    reason: str | None = None


class ValuationResult(BaseModel):
    """Classificação de valuation de um ativo por múltiplos (heurística MVP)."""

    ticker: str
    asset_class: str
    classification: str = "indeterminado"  # ver VALUATION_CLASSIFICATIONS
    metrics: list[MetricVerdict] = []
    confidence: str = "baixa"  # "alta" | "média" | "baixa"
    reason: str | None = None  # motivo geral, ex.: "classe sem múltiplos aplicáveis"
