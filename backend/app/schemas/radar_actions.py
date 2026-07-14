"""Schemas de payload das ações da tela Radar (v1.1, Fase 7).

Nenhuma regra nova aqui — só embrulha o que `WatchlistService` já espera
(`set_status`) e agrupa os resultados de `collect_data_for_asset` quando
chamado em lote (mesmo botão "Coletar dados de todos" do Streamlit).
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.app.infrastructure.database.models.watchlist_asset import WATCHLIST_STATUSES
from backend.app.schemas.watchlist import WatchlistDataCollectionResult


class WatchlistStatusUpdateRequest(BaseModel):
    """Payload de `PATCH /api/watchlist/{id}/status` — mesma transição
    livre (watching/candidate/blocked/discarded/bought, em qualquer
    direção) que `WatchlistService.set_status` já aceita."""

    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in WATCHLIST_STATUSES:
            raise ValueError(f"status deve ser um de: {', '.join(WATCHLIST_STATUSES)}")
        return value


class WatchlistCollectAllResult(BaseModel):
    """Resultado de `POST /api/watchlist/collect-all` — mesmo botão
    "Coletar dados de todos" do Streamlit, um `WatchlistDataCollectionResult`
    por ativo da watchlist."""

    results: list[WatchlistDataCollectionResult] = []
