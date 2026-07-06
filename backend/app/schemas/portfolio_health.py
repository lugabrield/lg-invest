"""Schemas do Portfolio Health Score (Sprint 24, Fase 8)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class HealthFactorView(BaseModel):
    name: str
    available: bool
    raw_value: Decimal | None = None
    score: Decimal | None = None
    weight_used: Decimal
    reason: str

    model_config = {"from_attributes": True}


class PortfolioHealthResultView(BaseModel):
    model_version: str
    overall_score: Decimal
    overall_classification: str
    factors: list[HealthFactorView]
    reasons: list[str]
    warnings: list[str]

    model_config = {"from_attributes": True}
