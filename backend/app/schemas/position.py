"""Schemas Pydantic de Position."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class PositionCreate(BaseModel):
    portfolio_id: int
    asset_id: int
    quantity: Decimal = Field(..., gt=0)
    average_price: Decimal = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    opened_at: date

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        return value.strip().upper()


class PositionRead(BaseModel):
    id: int
    portfolio_id: int
    asset_id: int
    quantity: Decimal
    average_price: Decimal
    currency: str
    opened_at: date

    model_config = {"from_attributes": True}
