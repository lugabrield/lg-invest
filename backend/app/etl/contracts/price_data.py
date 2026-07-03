"""Data contract de preço (Volume 4, seção 7).

Define o formato esperado de um preço vindo de qualquer fonte externa.
Todo provider deve retornar PriceData; nenhum dado entra na tabela
`prices` sem passar por este contrato e pelos validators.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PriceData(BaseModel):
    """Preço normalizado de um ativo numa data, independente da fonte."""

    ticker: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal = Field(...)
    adjusted_close: Decimal | None = None
    volume: Decimal | None = None
    currency: str
    source_name: str
    collected_at: datetime
