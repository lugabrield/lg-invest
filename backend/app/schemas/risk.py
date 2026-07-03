"""Schema de saída do Risk Engine v1 (Sprint 16 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

RISK_CLASSIFICATIONS = ("baixo", "médio", "alto", "indeterminado")


class RiskMetricVerdict(BaseModel):
    field: str
    label: str
    value: Decimal | None = None
    verdict: str  # "baixo" | "médio" | "alto" | "indeterminado"
    reason: str | None = None


class RiskResult(BaseModel):
    """Classificação de risco de balanço/mercado de um ativo (heurística MVP)."""

    ticker: str
    asset_class: str
    classification: str = "indeterminado"
    metrics: list[RiskMetricVerdict] = []
    confidence: str = "baixa"
    reason: str | None = None
