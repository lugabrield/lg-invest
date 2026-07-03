"""Schemas Pydantic de Price."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class PriceCreate(BaseModel):
    asset_id: int
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal = Field(..., ge=0)
    adjusted_close: Decimal | None = None
    volume: Decimal | None = None

    @field_validator("close")
    @classmethod
    def close_not_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("close não pode ser negativo.")
        return value


class PriceRead(BaseModel):
    id: int
    asset_id: int
    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    adjusted_close: Decimal | None
    volume: Decimal | None

    model_config = {"from_attributes": True}
