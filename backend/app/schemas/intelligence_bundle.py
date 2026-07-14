"""Schema de saída de `GET /api/intelligence` (v1.1, Fase 5).

Embrulha o que a tela Inteligência do Streamlit já compõe em
`frontend/streamlit_app/cache.py::cached_intelligence_bundle`:
`IntelligenceDashboardView` (Conviction Score v2 + alocação-alvo,
Sprint 19) e `IncomeAnalysisResultView` (renda de proventos, Sprint 24
Fase 7). Nenhum cálculo novo — só composição, igual às demais rotas.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.income_analysis import IncomeAnalysisResultView
from backend.app.schemas.intelligence_dashboard import IntelligenceDashboardView


class IntelligenceBundle(BaseModel):
    view: IntelligenceDashboardView
    income: IncomeAnalysisResultView
