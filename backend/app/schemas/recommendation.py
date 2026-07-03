"""Schemas Pydantic de Recommendation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class RecommendationCreate(BaseModel):
    date: date
    contribution_amount: Decimal = Field(..., gt=0)
    asset_id: int
    amount: Decimal = Field(..., ge=0)
    reason: str = Field(..., min_length=1)
    algo_version: str = Field(default="v1", max_length=20)


class RecommendationRead(BaseModel):
    id: int
    date: date
    contribution_amount: Decimal
    asset_id: int
    amount: Decimal
    reason: str
    algo_version: str

    model_config = {"from_attributes": True}
