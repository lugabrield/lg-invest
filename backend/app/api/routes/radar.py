"""Rotas de Radar/Watchlist (v1.1, Fase 7 — ver docs/API_CONTRACT.md).

Consome `WatchlistService` (CRUD + coleta de dados + troca de status) e
`RadarService` (classificação pura de candidatos), exatamente como
`frontend/streamlit_app/pages_impl/radar.py` já fazia. Nenhuma `Position`
é criada aqui, nenhum cálculo de patrimônio é duplicado — as rotas só
compõem o que os services já devolvem.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.schemas.radar import RadarEvaluation
from backend.app.schemas.radar_actions import (
    WatchlistCollectAllResult,
    WatchlistStatusUpdateRequest,
)
from backend.app.schemas.watchlist import (
    WatchlistAssetCreate,
    WatchlistAssetUpdate,
    WatchlistAssetView,
    WatchlistDataCollectionResult,
)
from backend.app.services.radar_service import RadarService
from backend.app.services.watchlist_service import WatchlistService

router = APIRouter(tags=["radar"])


@router.get("/watchlist", response_model=list[WatchlistAssetView])
def list_watchlist(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> list[WatchlistAssetView]:
    return WatchlistService(db).list_watchlist_assets(portfolio_id)


@router.post("/watchlist", response_model=WatchlistAssetView, status_code=201)
def add_watchlist_asset(
    payload: WatchlistAssetCreate,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> WatchlistAssetView:
    try:
        return WatchlistService(db).add_watchlist_asset(portfolio_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/watchlist/{watchlist_asset_id}", response_model=WatchlistAssetView)
def update_watchlist_asset(
    watchlist_asset_id: int,
    payload: WatchlistAssetUpdate,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> WatchlistAssetView:
    try:
        return WatchlistService(db).update_watchlist_asset(
            portfolio_id, watchlist_asset_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/watchlist/{watchlist_asset_id}/status", response_model=WatchlistAssetView)
def set_watchlist_status(
    watchlist_asset_id: int,
    payload: WatchlistStatusUpdateRequest,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> WatchlistAssetView:
    try:
        return WatchlistService(db).set_status(portfolio_id, watchlist_asset_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/watchlist/{watchlist_asset_id}", status_code=204)
def remove_watchlist_asset(
    watchlist_asset_id: int,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> None:
    removed = WatchlistService(db).remove_watchlist_asset(portfolio_id, watchlist_asset_id)
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"Watchlist asset {watchlist_asset_id} não encontrado."
        )


@router.post(
    "/watchlist/{watchlist_asset_id}/collect", response_model=WatchlistDataCollectionResult
)
def collect_watchlist_asset_data(
    watchlist_asset_id: int,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> WatchlistDataCollectionResult:
    try:
        return WatchlistService(db).collect_data_for_asset(portfolio_id, watchlist_asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/watchlist/collect-all", response_model=WatchlistCollectAllResult)
def collect_all_watchlist_data(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> WatchlistCollectAllResult:
    service = WatchlistService(db)
    entries = service.list_watchlist_assets(portfolio_id)
    results = [service.collect_data_for_asset(portfolio_id, e.id) for e in entries]
    return WatchlistCollectAllResult(results=results)


@router.get("/radar", response_model=RadarEvaluation)
def get_radar_evaluation(
    portfolio_id: int = Depends(get_portfolio_id), db: Session = Depends(get_db)
) -> RadarEvaluation:
    return RadarService(db).evaluate(portfolio_id)
