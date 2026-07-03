"""Schema de saída do painel de Inteligência (Sprint 19).

Agrega, por ativo, o LG Conviction Score v2 (Sprint 17) e o desvio de
alocação por classe (Target Allocation Engine, Sprint 17) numa única
estrutura de apresentação. Nenhum cálculo novo mora aqui — apenas a
composição do que os engines/serviços já existentes calculam.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from backend.app.schemas.ids_methodology import ConvictionPillarResult
from backend.app.schemas.target_allocation import TargetAllocationResult


class AssetIntelligence(BaseModel):
    """Visão consolidada de um ativo para o painel de Inteligência."""

    ticker: str
    asset_class: str
    current_weight: Decimal  # fração 0..1

    has_conviction_score: bool
    conviction_score: Decimal | None = None  # 0..100
    classification: str | None = None
    confidence: Decimal | None = None  # 0..1
    confidence_label: str | None = None
    quality: Decimal | None = None
    valuation: Decimal | None = None
    growth: Decimal | None = None
    risk: Decimal | None = None
    capital_reinvestment: Decimal | None = None
    explanation: list[ConvictionPillarResult] = []

    # motivo textual quando has_conviction_score é False (ex.: ativo sem
    # histórico de preço suficiente) — nunca um score inventado.
    unavailable_reason: str | None = None


class IntelligenceDashboardView(BaseModel):
    """Painel de Inteligência: Conviction Score + alocação-alvo por classe."""

    assets: list[AssetIntelligence]

    # média simples entre os ativos com score calculável; None se nenhum ativo tiver.
    average_conviction_score: Decimal | None = None
    coverage_pct: Decimal  # fração 0..1 do peso da carteira com conviction score calculável
    classification_counts: dict[str, int] = {}

    most_convicted: AssetIntelligence | None = None
    least_convicted: AssetIntelligence | None = None

    allocation_drift: TargetAllocationResult

    model_config = {"from_attributes": True}
