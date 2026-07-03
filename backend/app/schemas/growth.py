"""Schema de saída do Growth Engine v1 (Sprint 16 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

GROWTH_CLASSIFICATIONS = ("forte", "moderado", "fraco", "indeterminado")


class GrowthMetricVerdict(BaseModel):
    field: str
    label: str
    value: Decimal | None = None
    verdict: str  # "forte" | "moderada" | "fraca" | "indeterminado"
    reason: str | None = None


class GrowthResult(BaseModel):
    """Classificação de crescimento de um ativo (heurística MVP, via CAGR)."""

    ticker: str
    classification: str = "indeterminado"
    metrics: list[GrowthMetricVerdict] = []
    confidence: str = "baixa"
    reason: str | None = None
