"""Schema de saída do Quality Engine v1 (Sprint 16 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

QUALITY_CLASSIFICATIONS = ("alta", "média", "baixa", "indeterminado")


class QualityMetricVerdict(BaseModel):
    field: str
    label: str
    value: Decimal | None = None
    verdict: str  # "forte" | "média" | "fraca" | "indeterminado"
    reason: str | None = None


class QualityResult(BaseModel):
    """Classificação de qualidade de um ativo (heurística MVP)."""

    ticker: str
    asset_class: str
    classification: str = "indeterminado"
    metrics: list[QualityMetricVerdict] = []
    confidence: str = "baixa"
    reason: str | None = None
