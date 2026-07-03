"""Schemas Pydantic de Asset — validação de entrada e saída (Volume 16, seção 7)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES


class AssetCreate(BaseModel):
    """Payload para criação de um ativo."""

    ticker: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    asset_class: str
    country: str = Field(..., min_length=2, max_length=2)
    currency: str = Field(..., min_length=3, max_length=3)
    sector: str | None = None
    is_active: bool = True

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase_trimmed(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker não pode ser vazio.")
        return value

    @field_validator("asset_class")
    @classmethod
    def asset_class_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ASSET_CLASSES:
            raise ValueError(f"asset_class deve ser um de: {', '.join(ASSET_CLASSES)}")
        return value

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, value: str) -> str:
        return value.strip().upper()


class AssetRead(BaseModel):
    """Representação de leitura de um ativo já persistido."""

    id: int
    ticker: str
    name: str
    asset_class: str
    country: str
    currency: str
    sector: str | None
    is_active: bool

    model_config = {"from_attributes": True}
