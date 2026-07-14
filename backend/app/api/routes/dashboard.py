"""Rotas de Dashboard/Portfolio (v1.1, Fase 2 — ver docs/API_CONTRACT.md).

Camada fina sobre os services já existentes: monta a mesma composição de
`frontend/streamlit_app/cache.py::cached_dashboard_bundle`, sem
recalcular nada e sem nenhuma decisão de apresentação (cores/labels
ficam por conta do frontend).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.schemas.dashboard_bundle import DashboardBundle
from backend.app.schemas.portfolio_health import PortfolioHealthResultView
from backend.app.schemas.portfolio_risk import PortfolioRiskResultView
from backend.app.services import data_refresh_status_service, fx_settings_service
from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.data_quality_service import DataQualityService
from backend.app.services.intelligence_dashboard_service import build_intelligence_dashboard
from backend.app.services.portfolio_diagnostics_service import get_portfolio_diagnostics
from backend.app.services.portfolio_health_service import PortfolioHealthService
from backend.app.services.portfolio_risk_service import PortfolioRiskService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardBundle)
def get_dashboard(
    db: Session = Depends(get_db),
    portfolio_id: int = Depends(get_portfolio_id),
) -> DashboardBundle:
    exchange_rate = fx_settings_service.get_usd_brl_rate()

    view = build_dashboard_view(db, portfolio_id, exchange_rate)
    diagnostics = get_portfolio_diagnostics(db, portfolio_id, exchange_rate)
    intelligence = build_intelligence_dashboard(db, portfolio_id)
    data_quality = DataQualityService(db).evaluate_portfolio(portfolio_id)
    health_result = PortfolioHealthService(db).evaluate(portfolio_id)
    risk_result = PortfolioRiskService(db).evaluate(portfolio_id)
    refresh_status = data_refresh_status_service.get_last_refresh_status()

    return DashboardBundle(
        view=view,
        diagnostics=diagnostics,
        intelligence=intelligence,
        data_quality=data_quality,
        health=PortfolioHealthResultView.model_validate(health_result),
        risk=PortfolioRiskResultView.model_validate(risk_result),
        data_refresh_status=refresh_status,
    )
