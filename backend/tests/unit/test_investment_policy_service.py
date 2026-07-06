"""Testes de InvestmentPolicyRepository e InvestmentPolicyService (Sprint 24, Fase 3).

Cobre: criação com defaults sensatos na primeira leitura (nunca
inventados "do nada" — documentados em `investment_policy_service.py`),
persistência real via banco (não JSON), atualização parcial
(`exclude_unset`) e o fato de que os defaults nunca são reescritos como
"recomendação financeira" (apenas ponto de partida editável).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.infrastructure.database.models import Portfolio
from backend.app.infrastructure.repositories.investment_policy_repository import (
    InvestmentPolicyRepository,
)
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate
from backend.app.services.investment_policy_service import InvestmentPolicyService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def test_get_or_create_creates_defaults_when_missing(db_session):
    portfolio_id = _seed_portfolio(db_session)
    view = InvestmentPolicyService(db_session).get_or_create(portfolio_id)

    assert view.portfolio_id == portfolio_id
    assert view.investor_profile == "Buy and Hold - crescimento de longuíssimo prazo"
    assert view.horizon_years == 50
    assert view.base_currency == "BRL"
    assert view.risk_tolerance == "moderado-alto"
    assert view.max_asset_weight == Decimal("0.15")
    assert view.max_crypto_weight == Decimal("0.05")
    assert "NÃO é uma recomendação financeira" in view.notes


def test_get_or_create_persists_row_in_database(db_session):
    portfolio_id = _seed_portfolio(db_session)
    InvestmentPolicyService(db_session).get_or_create(portfolio_id)

    stored = InvestmentPolicyRepository(db_session).get_by_portfolio(portfolio_id)
    assert stored is not None
    assert stored.portfolio_id == portfolio_id


def test_get_or_create_does_not_duplicate_row_on_second_call(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = InvestmentPolicyService(db_session)
    service.get_or_create(portfolio_id)
    service.get_or_create(portfolio_id)

    repo = InvestmentPolicyRepository(db_session)
    rows = (
        db_session.query(type(repo.get_by_portfolio(portfolio_id)))
        .filter_by(portfolio_id=portfolio_id)
        .all()
    )
    assert len(rows) == 1


def test_update_changes_only_provided_fields(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = InvestmentPolicyService(db_session)
    service.get_or_create(portfolio_id)

    updated = service.update(
        portfolio_id,
        InvestmentPolicyUpdate(max_crypto_weight=Decimal("0.08"), risk_tolerance="alto"),
    )

    assert updated.max_crypto_weight == Decimal("0.08")
    assert updated.risk_tolerance == "alto"
    # Campos não enviados permanecem com o default original.
    assert updated.horizon_years == 50
    assert updated.max_asset_weight == Decimal("0.15")


def test_update_creates_policy_first_if_not_existing(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = InvestmentPolicyService(db_session)

    updated = service.update(portfolio_id, InvestmentPolicyUpdate(horizon_years=60))

    assert updated.horizon_years == 60
    assert updated.investor_profile == "Buy and Hold - crescimento de longuíssimo prazo"


def test_repository_update_persists_changes(db_session):
    portfolio_id = _seed_portfolio(db_session)
    repo = InvestmentPolicyRepository(db_session)
    service = InvestmentPolicyService(db_session)
    service.get_or_create(portfolio_id)

    policy = repo.get_by_portfolio(portfolio_id)
    policy.horizon_years = 45
    repo.update(policy)

    reloaded = repo.get_by_portfolio(portfolio_id)
    assert reloaded.horizon_years == 45
