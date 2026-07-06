"""Cache de leitura para os agregados mais caros da UI (Sprint 24, Fase 10).

Nenhuma engine/serviço muda de comportamento aqui — isto é só uma camada
de apresentação sobre chamadas já existentes. O Dashboard (Fase 9) passou
a compor 6 serviços por carregamento (view, diagnósticos, inteligência,
qualidade de dado, saúde da carteira, risco da carteira), e a
Inteligência passou a compor 2 (inteligência, renda) — sem cache, cada
clique de navegação recalculava tudo do zero.

Os wrappers abrem sua própria sessão de banco (nunca recebem `db` como
argumento, que não é hasheável pelo `st.cache_data`) e devolvem só
schemas Pydantic/dataclasses imutáveis. TTL curto (5 min) funciona como
rede de segurança, mas nunca é a única defesa contra dado desatualizado:
qualquer ação que muda dado relevante para essas telas (preços,
posições, fundamentos, política de investimento, alocação-alvo,
premissas do Monte Carlo) chama `clear_all_caches()` explicitamente logo
após persistir, para refletir na hora — sem esperar o TTL expirar.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from backend.app.services.dashboard_view_service import build_dashboard_view
from backend.app.services.data_quality_service import DataQualityService
from backend.app.services.income_analysis_service import IncomeAnalysisService
from backend.app.services.intelligence_dashboard_service import build_intelligence_dashboard
from backend.app.services.portfolio_diagnostics_service import get_portfolio_diagnostics
from backend.app.services.portfolio_health_service import PortfolioHealthService
from backend.app.services.portfolio_risk_service import PortfolioRiskService
from frontend.streamlit_app.db import session_scope

# Rede de segurança: mesmo sem nenhuma ação explícita de invalidação (ex.:
# preço atualizado por um processo externo ao Streamlit), o cache nunca
# fica desatualizado por mais que isso.
CACHE_TTL_SECONDS = 300


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_dashboard_bundle(portfolio_id: int, exchange_rate: Decimal):
    """View + diagnósticos + inteligência + qualidade + saúde + risco, em uma só leitura.

    Usado pela tela Dashboard (Fase 9). Composição de 6 serviços — cara o
    suficiente para valer a pena cachear no MVP (Fase 10).
    """
    with session_scope() as db:
        view = build_dashboard_view(db, portfolio_id, exchange_rate)
        diagnostics = get_portfolio_diagnostics(db, portfolio_id, exchange_rate)
        intelligence = build_intelligence_dashboard(db, portfolio_id)
        data_quality = DataQualityService(db).evaluate_portfolio(portfolio_id)
        health_result = PortfolioHealthService(db).evaluate(portfolio_id)
        risk_result = PortfolioRiskService(db).evaluate(portfolio_id)
    return view, diagnostics, intelligence, data_quality, health_result, risk_result


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_intelligence_bundle(portfolio_id: int):
    """Inteligência da carteira + análise de renda, em uma só leitura.

    Usado pela tela Inteligência (Fase 9/7).
    """
    with session_scope() as db:
        view = build_intelligence_dashboard(db, portfolio_id)
        income_result = IncomeAnalysisService(db).evaluate(portfolio_id)
    return view, income_result


def clear_all_caches() -> None:
    """Invalida os caches acima.

    Chamar logo após qualquer ação que muda dado que essas telas leem:
    preços (automáticos/manuais), posições, fundamentos, política de
    investimento, alocação-alvo (simples ou detalhada) e premissas do
    Monte Carlo.
    """
    cached_dashboard_bundle.clear()
    cached_intelligence_bundle.clear()
