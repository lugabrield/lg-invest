"""Teste de regressão do Decision Engine sobre carteira de exemplo.

Verifica invariantes estáveis da recomendação (não valores exatos, que
dependem de pesos): soma <= aporte, distribuição não vazia, auditoria
completa e determinismo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.services.decision_service import DecisionService
from backend.tests.regression._helpers import build_session_from_fixture


def test_recommendation_invariants_brazil():
    session, pid = build_session_from_fixture("sample_portfolio_brazil.json")
    try:
        result = DecisionService(session).recommend(pid, Decimal("1000"), persist=False)
        total = sum((i.amount for i in result.items), start=Decimal("0"))
        assert total <= Decimal("1000")
        assert total == result.allocated_amount
        assert result.audit.model_version == "decision_v1"
        assert result.audit.contribution_amount == Decimal("1000")
    finally:
        session.close()


def test_recommendation_is_deterministic():
    """Mesma carteira e mesmo aporte devem gerar a mesma distribuição."""
    session1, pid1 = build_session_from_fixture("sample_portfolio_brazil.json")
    session2, pid2 = build_session_from_fixture("sample_portfolio_brazil.json")
    try:
        r1 = DecisionService(session1).recommend(pid1, Decimal("1000"), persist=False)
        r2 = DecisionService(session2).recommend(pid2, Decimal("1000"), persist=False)
        d1 = {i.ticker: i.amount for i in r1.items}
        d2 = {i.ticker: i.amount for i in r2.items}
        assert d1 == d2
    finally:
        session1.close()
        session2.close()


def test_blocked_asset_excluded_in_fixture():
    session, pid = build_session_from_fixture("sample_portfolio_global.json")
    try:
        result = DecisionService(session).recommend(
            pid, Decimal("1000"), blocked={"VOO"}, persist=False
        )
        tickers = {i.ticker for i in result.items}
        assert "VOO" not in tickers
    finally:
        session.close()


def test_v2_recommendation_invariants_brazil():
    """Decision Engine 2.0 (Sprint 18) sobre a mesma carteira de exemplo.

    Sem fundamentos coletados na fixture, todo Conviction Score cai de
    volta na proxy de preço (graceful degradation) — o teste verifica
    que isso não quebra as invariantes básicas da recomendação.
    """
    session, pid = build_session_from_fixture("sample_portfolio_brazil.json")
    try:
        result = DecisionService(session).recommend_v2(pid, Decimal("1000"), persist=False)
        total = sum((i.amount for i in result.items), start=Decimal("0"))
        assert total <= Decimal("1000")
        assert total == result.allocated_amount
        assert result.audit.model_version == "decision_v2"
        assert result.audit.contribution_amount == Decimal("1000")
    finally:
        session.close()


def test_v2_recommendation_is_deterministic():
    session1, pid1 = build_session_from_fixture("sample_portfolio_brazil.json")
    session2, pid2 = build_session_from_fixture("sample_portfolio_brazil.json")
    try:
        r1 = DecisionService(session1).recommend_v2(pid1, Decimal("1000"), persist=False)
        r2 = DecisionService(session2).recommend_v2(pid2, Decimal("1000"), persist=False)
        d1 = {i.ticker: i.amount for i in r1.items}
        d2 = {i.ticker: i.amount for i in r2.items}
        assert d1 == d2
    finally:
        session1.close()
        session2.close()
