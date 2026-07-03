"""Schemas de saída do pipeline de market data (Sprint 12).

Move `UpdateResult`/`BatchUpdateResult` de dataclasses soltas dentro de
`market_data_service.py` para Pydantic, seguindo o mesmo padrão dos
demais schemas de serviço (`portfolio_summary`, `lg_score`,
`recommendation_result`). Acrescenta `PriceStatus` (estado do preço de
um ticker, para Dashboard/Ativos) e `FxQuote` (cotação de câmbio com
origem e timestamp, para a cadeia de fallback BCB -> Yahoo -> manual).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# Estado do preço de um ativo:
# - "automatic": veio do provider (Yahoo) e está atualizado.
# - "manual": ativo com is_manual=True; preço cadastrado pelo usuário.
# - "estimated": nenhum preço salvo; Dashboard usa average_price como estimativa.
# - "missing": nenhum preço e nenhum average_price disponível.
PRICE_STATUSES = ("automatic", "manual", "estimated", "missing")

# Origem de uma cotação de câmbio, na ordem de prioridade do fallback.
FX_SOURCES = ("bcb", "yahoo", "manual")


class UpdateResult(BaseModel):
    """Resultado da atualização de preços de um único ativo."""

    ticker: str
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    skipped_manual: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return self.model_dump()


class BatchUpdateResult(BaseModel):
    """Resultado agregado da atualização de preços de um lote de ativos."""

    results: list[UpdateResult] = Field(default_factory=list)

    @property
    def total_inserted(self) -> int:
        return sum(r.inserted for r in self.results)

    @property
    def total_updated(self) -> int:
        return sum(r.updated for r in self.results)

    @property
    def total_skipped_manual(self) -> int:
        return sum(1 for r in self.results if r.skipped_manual)

    @property
    def failed(self) -> list[str]:
        return [r.ticker for r in self.results if r.error]

    def as_dict(self) -> dict:
        return {
            "total_inserted": self.total_inserted,
            "total_updated": self.total_updated,
            "total_skipped_manual": self.total_skipped_manual,
            "failed": self.failed,
            "results": [r.as_dict() for r in self.results],
        }


class FxQuote(BaseModel):
    """Cotação de câmbio com origem e momento da coleta/persistência."""

    pair: str = "USDBRL"
    rate: Decimal
    source: str  # "bcb" | "yahoo" | "manual"
    quote_date: datetime  # data/hora a que a cotação se refere
    fetched_at: datetime  # momento em que foi coletada/persistida
    is_override: bool = False  # True quando o usuário sobrescreveu manualmente

    model_config = {"from_attributes": True}
