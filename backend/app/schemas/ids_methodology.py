"""Schemas de saída da IDS Methodology / LG Conviction Score (Sprint 12).

Espelha `schemas/lg_score.py`: estruturas serializáveis com notas
parciais, score final, confiança, classificação e explicação por
pilar — sem recalcular nada. `PillarWeights`/`AssetProfileWeights`
descrevem os pesos usados em um cálculo específico, para auditoria e
explicabilidade ("por que este ativo pesou mais Risco do que Growth?").
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class PillarWeights(BaseModel):
    """Pesos usados no cálculo de um Conviction Score específico."""

    quality: float
    valuation: float
    growth: float
    risk: float
    capital_reinvestment: float


class AssetProfileWeights(BaseModel):
    """Pesos do perfil de uma classe de ativo (para exibição/documentação)."""

    asset_class: str
    weights: PillarWeights


class ConvictionPillarResult(BaseModel):
    name: str
    score: Decimal  # 0..100
    confidence: Decimal  # 0..1
    reasons: list[str]


class ConvictionScoreResult(BaseModel):
    """LG Conviction Score de um ativo: fundação da IDS Methodology (Sprint 12).

    Paralelo ao LG Score, não um substituto — o Decision Engine
    continua usando exclusivamente o LG Score. Ver docs/IDS_METHODOLOGY.md.
    """

    ticker: str
    conviction_score: Decimal  # 0..100
    quality: Decimal
    valuation: Decimal
    growth: Decimal
    risk: Decimal
    capital_reinvestment: Decimal
    confidence: Decimal  # 0..1
    confidence_label: str
    classification: str
    model_version: str
    explanation: list[ConvictionPillarResult]

    model_config = {"from_attributes": True}
