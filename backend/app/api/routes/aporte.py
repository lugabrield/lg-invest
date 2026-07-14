"""Rotas de Aporte (v1.1, Fase 3 — ver docs/API_CONTRACT.md).

`POST /api/aporte` chama o mesmo `DecisionService` (Decision Engine
v1/v2/v3, inalterado) e o mesmo `allocation_projection_service`
("como a carteira ficaria depois", também inalterado) que
`frontend/streamlit_app/pages_impl/aporte.py` já usa — nenhuma regra de
decisão é recalculada ou duplicada aqui, só exposta via HTTP.

`GET /api/assets` devolve o universo de ativos cadastrados, usado pela UI
só para popular o seletor de "ativos bloqueados" (mesma lista que
`AssetRepository.list_all()` já fornecia para o `st.multiselect` na tela
Streamlit).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.aporte_bundle import AporteBundle, AporteRequest, AssetSummary
from backend.app.services import fx_settings_service
from backend.app.services.allocation_projection_service import build_allocation_projection
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.decision_service import DecisionService

router = APIRouter(tags=["aporte"])


@router.get("/assets", response_model=list[AssetSummary])
def list_assets(db: Session = Depends(get_db)) -> list[AssetSummary]:
    assets = AssetRepository(db).list_all()
    return [AssetSummary.model_validate(asset) for asset in assets]


@router.post("/aporte", response_model=AporteBundle)
def simulate_aporte(
    payload: AporteRequest,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> AporteBundle:
    exchange_rate = fx_settings_service.get_usd_brl_rate()
    view_before = build_dashboard_view(db, portfolio_id, exchange_rate)

    service = DecisionService(db)
    blocked = {ticker.upper() for ticker in payload.blocked}

    if payload.engine_version == "v3":
        result = service.recommend_v3(
            portfolio_id,
            payload.amount,
            blocked=blocked,
            persist=payload.persist,
            allow_watchlist_candidates=payload.allow_watchlist_candidates,
        )
    else:
        recommend_fn = {
            "v1": service.recommend,
            "v2": service.recommend_v2,
        }[payload.engine_version]
        result = recommend_fn(
            portfolio_id,
            payload.amount,
            blocked=blocked,
            persist=payload.persist,
        )

    projection = build_allocation_projection(view_before, result) if result.items else None
    return AporteBundle(result=result, projection=projection)
