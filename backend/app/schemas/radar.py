"""Schemas de saída do Radar Engine (Sprint 25, Parte 2.4)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from backend.app.engines.radar.inputs import RADAR_CLASSIFICATIONS  # noqa: F401 (reexport)


class RadarClassificationResult(BaseModel):
    """Classificação de um único ativo (posição existente ou candidato
    da Watchlist) dentro do Radar."""

    ticker: str
    name: str
    asset_class: str
    watchlist_status: str | None
    is_current_holding: bool
    current_weight: Decimal | None = None

    classification: str  # ver RADAR_CLASSIFICATIONS
    effective_score: Decimal | None = None
    score_source: str | None = None  # "conviction_score" | "lg_score" | None
    confidence: Decimal | None = None

    reasons: list[str] = []


class RadarEvaluation(BaseModel):
    """Resultado agregado do Radar — lista completa + contagem por
    classificação, para a UI renderizar seções (Já tenho / Novo
    candidato / Monitorar / Evitar / Bloqueado / Dado insuficiente)."""

    candidates: list[RadarClassificationResult] = []

    def count_by_classification(self, classification: str) -> int:
        return sum(1 for c in self.candidates if c.classification == classification)

    def by_classification(self, classification: str) -> list[RadarClassificationResult]:
        return [c for c in self.candidates if c.classification == classification]
