"""Schemas de saída do Decision Engine (Volume 7 §4; Volume 18 §10).

Estruturas serializáveis com a distribuição recomendada, justificativa
por ativo, score de compra, alertas, ativos ignorados, nível de
confiança e o log de auditoria completo.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    ticker: str
    amount: Decimal
    weight: Decimal  # fração do aporte
    buy_score: Decimal  # 0..1
    lg_score: Decimal  # 0..100
    conviction_score: Decimal | None = None  # 0..100, só preenchido pelo Decision Engine 2.0
    reasons: list[str]


class IgnoredItem(BaseModel):
    ticker: str
    reason: str


class DecisionAudit(BaseModel):
    """Log auditável da recomendação (Volume 18, seção 10)."""

    contribution_amount: Decimal
    eligible_tickers: list[str]
    blocked_tickers: list[str]
    model_version: str
    weights: dict[str, float]


class RecommendationResult(BaseModel):
    contribution_amount: Decimal
    allocated_amount: Decimal  # soma efetivamente distribuída (<= contribution_amount)
    items: list[RecommendationItem]
    ignored: list[IgnoredItem]
    alerts: list[str]
    confidence: Decimal  # 0..1
    confidence_label: str
    explanation: str  # resumo em linguagem natural
    audit: DecisionAudit

    model_config = {"from_attributes": True}
