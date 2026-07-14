"""Schema do agregado `GET /api/dashboard` (v1.1, Fase 2 — ver docs/API_CONTRACT.md).

Reúne, num único payload, exatamente os mesmos 7 pedaços que
`frontend/streamlit_app/cache.py::cached_dashboard_bundle` já compõe
para a tela Dashboard (mais o status da Central de Dados) — nenhum
cálculo novo, só o "pacote" para o frontend novo.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.dashboard_view import DashboardView
from backend.app.schemas.data_quality import PortfolioDataQualitySummary
from backend.app.schemas.data_refresh import LastRefreshStatus
from backend.app.schemas.intelligence_dashboard import IntelligenceDashboardView
from backend.app.schemas.portfolio_diagnostics import PortfolioDiagnostics
from backend.app.schemas.portfolio_health import PortfolioHealthResultView
from backend.app.schemas.portfolio_risk import PortfolioRiskResultView


class DashboardBundle(BaseModel):
    view: DashboardView
    diagnostics: PortfolioDiagnostics
    intelligence: IntelligenceDashboardView
    data_quality: PortfolioDataQualitySummary
    health: PortfolioHealthResultView
    risk: PortfolioRiskResultView
    data_refresh_status: LastRefreshStatus
