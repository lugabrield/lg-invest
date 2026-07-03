"""Schemas de linha de importação (Volume 4, seção 11/13).

Representam uma linha bruta de um arquivo CSV/Excel já validada e
tipada. A validação de schema/tipo acontece aqui; regras de negócio
adicionais (ticker existente, duplicidade) ficam nos validators.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES


class PositionImportRow(BaseModel):
    """Uma linha do template de importação de posições."""

    ticker: str = Field(..., min_length=1, max_length=20)
    quantity: Decimal = Field(..., gt=0)
    average_price: Decimal = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    opened_at: date

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker vazio")
        return value

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        return value.strip().upper()


class AssetImportRow(BaseModel):
    """Uma linha do template de importação de ativos."""

    ticker: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    asset_class: str
    country: str = Field(..., min_length=2, max_length=2)
    currency: str = Field(..., min_length=3, max_length=3)
    sector: str | None = None

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("asset_class")
    @classmethod
    def asset_class_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ASSET_CLASSES:
            raise ValueError(f"asset_class inválida: {value}")
        return value

    @field_validator("currency", "country")
    @classmethod
    def upper(cls, value: str) -> str:
        return value.strip().upper()
