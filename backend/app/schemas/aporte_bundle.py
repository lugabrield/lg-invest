"""Schemas da rota `POST /api/aporte` (v1.1, Fase 3 — ver docs/API_CONTRACT.md).

Nenhuma regra nova mora aqui: `AporteRequest` só valida a entrada que a
Streamlit já coleta em `pages_impl/aporte.py` (valor, bloqueados, versão do
motor, persistência, watchlist), e `AporteBundle` embrulha exatamente o que
`DecisionService` (Decision Engine, inalterado) e
`allocation_projection_service` (apresentação, também inalterado) já
devolvem — `RecommendationResult` e `AllocationProjection` já são
`pydantic.BaseModel`, então não há conversão/adaptação nenhuma aqui.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from backend.app.schemas.allocation_projection import AllocationProjection
from backend.app.schemas.recommendation_result import RecommendationResult

EngineVersion = Literal["v1", "v2", "v3"]


class AporteRequest(BaseModel):
    amount: Decimal
    blocked: list[str] = []
    engine_version: EngineVersion = "v3"
    # Mesmo default do checkbox "Salvar recomendação (auditoria)" na tela
    # Streamlit (marcado por padrão) — quem simula sem querer persistir
    # manda `persist=false` explicitamente.
    persist: bool = True
    # Só tem efeito quando `engine_version="v3"` — mesmo comportamento do
    # checkbox "Permitir ativos novos da watchlist" (desmarcado por padrão).
    allow_watchlist_candidates: bool = False


class AporteBundle(BaseModel):
    result: RecommendationResult
    # `None` quando a recomendação não alocou nenhum item — não há "antes x
    # depois" para projetar (mesma condição usada em `aporte.py`:
    # `if result.items:`).
    projection: AllocationProjection | None = None


class AssetSummary(BaseModel):
    """Só o necessário para o seletor de 'ativos bloqueados' na UI — não é
    o cadastro completo de Asset (isso fica para quando a tela Ativos for
    migrada)."""

    ticker: str
    name: str
    asset_class: str

    model_config = {"from_attributes": True}
