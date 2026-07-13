"""Schemas Pydantic de WatchlistAsset (Sprint 25, Parte 2.1-2.3).

A Watchlist é um cadastro de ativos CANDIDATOS — nunca uma posição.
Nenhum schema aqui participa do cálculo de patrimônio ou de posições
(ver `backend/app/schemas/position.py` para isso, que continua
totalmente separado).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.asset import ASSET_CLASSES
from backend.app.infrastructure.database.models.watchlist_asset import WATCHLIST_STATUSES


class WatchlistAssetCreate(BaseModel):
    """Payload para cadastrar um novo candidato na Watchlist."""

    ticker: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    asset_class: str
    country: str = Field(..., min_length=2, max_length=2)
    currency: str = Field(..., min_length=3, max_length=3)
    sector: str | None = None
    status: str = "watching"
    priority: int = 0
    thesis: str | None = None
    notes: str | None = None
    source: str = "manual"

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase_trimmed(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker não pode ser vazio.")
        return value

    @field_validator("name")
    @classmethod
    def name_trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name não pode ser vazio.")
        return value

    @field_validator("asset_class")
    @classmethod
    def asset_class_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("asset_class não pode ser vazio.")
        if value not in ASSET_CLASSES:
            raise ValueError(f"asset_class deve ser um de: {', '.join(ASSET_CLASSES)}")
        return value

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in WATCHLIST_STATUSES:
            raise ValueError(f"status deve ser um de: {', '.join(WATCHLIST_STATUSES)}")
        return value

    @field_validator("source")
    @classmethod
    def source_trimmed(cls, value: str) -> str:
        value = value.strip().lower()
        return value or "manual"


class WatchlistAssetUpdate(BaseModel):
    """Payload de atualização — só os campos enviados são alterados."""

    name: str | None = None
    asset_class: str | None = None
    country: str | None = None
    currency: str | None = None
    sector: str | None = None
    status: str | None = None
    priority: int | None = None
    thesis: str | None = None
    notes: str | None = None

    @field_validator("asset_class")
    @classmethod
    def asset_class_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in ASSET_CLASSES:
            raise ValueError(f"asset_class deve ser um de: {', '.join(ASSET_CLASSES)}")
        return value

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in WATCHLIST_STATUSES:
            raise ValueError(f"status deve ser um de: {', '.join(WATCHLIST_STATUSES)}")
        return value

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class WatchlistAssetView(BaseModel):
    """Representação de leitura de um WatchlistAsset já persistido."""

    id: int
    portfolio_id: int
    ticker: str
    name: str
    asset_class: str
    country: str
    currency: str
    sector: str | None
    status: str
    priority: int
    thesis: str | None
    notes: str | None
    source: str
    # True quando o ticker já existe em `assets`/carteira — sinalizado pelo
    # serviço, nunca calculado dentro do próprio schema (schema não acessa banco).
    already_in_portfolio: bool = False
    # Quando a última coleta de dados rodou com sucesso — `None` até a
    # primeira coleta (ver `WatchlistService.collect_data_for_asset`).
    last_collected_at: datetime | None = None

    model_config = {"from_attributes": True}


class WatchlistDataCollectionResult(BaseModel):
    """Resultado da coleta de dados (Parte 2.3) para um candidato da Watchlist.

    Nunca inventa valor: quando um passo não é possível (sem provider,
    ativo não aplicável, falha externa), o campo correspondente fica
    `None`/`False` e o motivo vai em `notes` — a UI deve mostrar "dado
    indisponível", nunca um placeholder fabricado.
    """

    ticker: str
    asset_ensured: bool = False
    price_collected: bool = False
    fundamentals_collected: bool = False
    lg_score: Decimal | None = None
    conviction_score: Decimal | None = None
    confidence: Decimal | None = None
    low_confidence: bool = False
    notes: list[str] = []
