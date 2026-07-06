"""Schemas do Portfolio Risk Engine (Sprint 24, Fase 6 — "Risk Engine 2.0")."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class RiskFactorView(BaseModel):
    """Um dos 4 fatores de risco combinados no score composto."""

    name: str
    available: bool
    raw_value: Decimal | None = None
    score: Decimal | None = None
    classification: str | None = None
    weight_used: Decimal
    reason: str

    model_config = {"from_attributes": True}


class PortfolioRiskResultView(BaseModel):
    """Resultado agregado de risco da carteira, pronto para exibição."""

    model_version: str
    overall_score: Decimal
    overall_classification: str
    factors: list[RiskFactorView]
    declared_risk_tolerance: str | None = None
    tolerance_alert: str | None = None
    reasons: list[str]
    warnings: list[str]

    model_config = {"from_attributes": True}
