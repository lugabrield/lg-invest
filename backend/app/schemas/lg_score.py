"""Schemas de saída do LG Score Engine (Volume 6, seção 13).

Estruturas serializáveis com notas parciais, score final, confiança,
classificação e explicação por pilar. Consumidas por CLI, API e UI —
sem recalcular nada.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class PillarResult(BaseModel):
    name: str
    score: Decimal  # 0..100
    confidence: Decimal  # 0..1
    reasons: list[str]


class LGScoreResult(BaseModel):
    ticker: str
    lg_score: Decimal  # 0..100
    quality: Decimal
    valuation: Decimal
    growth: Decimal
    risk: Decimal
    allocation: Decimal
    confidence: Decimal  # 0..1
    confidence_label: str
    classification: str
    model_version: str
    explanation: list[PillarResult]

    model_config = {"from_attributes": True}
