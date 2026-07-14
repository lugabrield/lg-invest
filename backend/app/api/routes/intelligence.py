"""Rota de Inteligência (v1.1, Fase 5 — ver docs/API_CONTRACT.md).

Mesma composição de `frontend/streamlit_app/cache.py::cached_intelligence_bundle`:
`build_intelligence_dashboard()` (Conviction Score v2 + alocação-alvo,
já `pydantic.BaseModel`) e `IncomeAnalysisService.evaluate()` (renda de
proventos — dataclass puro do engine, convertido via
`IncomeAnalysisResultView.model_validate()`, mesmo padrão de
`AssetSummary.model_validate(asset)` em `routes/aporte.py`). Nenhum
cálculo novo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.schemas.income_analysis import IncomeAnalysisResultView
from backend.app.schemas.intelligence_bundle import IntelligenceBundle
from backend.app.services.income_analysis_service import IncomeAnalysisService
from backend.app.services.intelligence_dashboard_service import build_intelligence_dashboard

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence", response_model=IntelligenceBundle)
def get_intelligence(
    db: Session = Depends(get_db),
    portfolio_id: int = Depends(get_portfolio_id),
) -> IntelligenceBundle:
    view = build_intelligence_dashboard(db, portfolio_id)
    income_result = IncomeAnalysisService(db).evaluate(portfolio_id)

    return IntelligenceBundle(
        view=view,
        income=IncomeAnalysisResultView.model_validate(income_result),
    )
