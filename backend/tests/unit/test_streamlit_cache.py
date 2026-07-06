"""Testes do módulo de cache da UI (Sprint 24, Fase 10).

Segue a mesma convenção da camada Streamlit (ver test_streamlit_smoke.py):
não testamos a renderização em si, só o "contrato" do módulo — aqui,
que as funções expostas são de fato memoizadas pelo `st.cache_data`
(têm `.clear()`) e que `clear_all_caches()` não lança erro. Os wrappers
abrem sua própria sessão via `SessionLocal` (não a fixture `db_session`,
que usa um engine SQLite em memória isolado), então o cálculo em si já
está coberto pelos testes dos serviços que cada bundle compõe
(`test_dashboard_view_service.py`, `test_portfolio_health_service.py`,
`test_portfolio_risk_service.py`, `test_intelligence_dashboard_service.py`,
`test_income_analysis_service.py`).
"""

from __future__ import annotations

from frontend.streamlit_app.cache import (
    cached_dashboard_bundle,
    cached_intelligence_bundle,
    clear_all_caches,
)


def test_cached_bundles_are_memoized_by_streamlit():
    # st.cache_data envolve a função original num wrapper com `.clear()` —
    # uma função comum não teria esse atributo.
    assert hasattr(cached_dashboard_bundle, "clear")
    assert hasattr(cached_intelligence_bundle, "clear")


def test_clear_all_caches_does_not_raise():
    clear_all_caches()
