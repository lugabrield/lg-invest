"""Schemas Pydantic de Portfolio."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    base_currency: str = Field(default="BRL", min_length=3, max_length=3)
    strategy: str | None = Field(default=None, max_length=60)

    @field_validator("base_currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        return value.strip().upper()


class PortfolioRead(BaseModel):
    id: int
    name: str
    base_currency: str
    strategy: str | None

    model_config = {"from_attributes": True}
