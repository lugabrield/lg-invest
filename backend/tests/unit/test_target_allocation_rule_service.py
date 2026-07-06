"""Testes de TargetAllocationRuleRepository e TargetAllocationRuleService
(Sprint 24, Fase 3).

Cobre: validação de dimension_type, validação de pesos negativos e
min/target <= max, upsert (nunca duplica regra para a mesma
dimensão/chave), delete e o fato de que nenhuma regra é pré-cadastrada
com valor inventado — a tabela começa sempre vazia por carteira.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Portfolio
from backend.app.infrastructure.repositories.target_allocation_rule_repository import (
    TargetAllocationRuleRepository,
)
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def test_list_rules_empty_by_default(db_session):
    portfolio_id = _seed_portfolio(db_session)
    rules = TargetAllocationRuleService(db_session).list_rules(portfolio_id)
    assert rules == []


def test_set_rule_creates_new_rule(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    rule = service.set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        target_weight=Decimal("0.20"),
        max_weight=Decimal("0.30"),
        priority=5,
    )

    assert rule.dimension_type == "class"
    assert rule.dimension_key == "fii"
    assert rule.target_weight == Decimal("0.20")
    assert rule.priority == 5


def test_set_rule_upserts_instead_of_duplicating(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    service.set_rule(portfolio_id, dimension_type="class", dimension_key="fii", priority=1)
    service.set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        priority=9,
        target_weight=Decimal("0.15"),
    )

    rules = service.list_rules(portfolio_id)
    assert len(rules) == 1
    assert rules[0].priority == 9
    assert rules[0].target_weight == Decimal("0.15")


def test_set_rule_rejects_invalid_dimension_type(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    with pytest.raises(ValueError):
        service.set_rule(portfolio_id, dimension_type="sector", dimension_key="tech")


def test_set_rule_rejects_empty_dimension_key(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    with pytest.raises(ValueError):
        service.set_rule(portfolio_id, dimension_type="class", dimension_key="   ")


def test_set_rule_rejects_negative_weight(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    with pytest.raises(ValueError):
        service.set_rule(
            portfolio_id,
            dimension_type="class",
            dimension_key="fii",
            target_weight=Decimal("-0.10"),
        )


def test_set_rule_rejects_min_greater_than_max(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    with pytest.raises(ValueError):
        service.set_rule(
            portfolio_id,
            dimension_type="class",
            dimension_key="fii",
            min_weight=Decimal("0.40"),
            max_weight=Decimal("0.30"),
        )


def test_set_rule_rejects_target_greater_than_max(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    with pytest.raises(ValueError):
        service.set_rule(
            portfolio_id,
            dimension_type="class",
            dimension_key="fii",
            target_weight=Decimal("0.50"),
            max_weight=Decimal("0.30"),
        )


def test_delete_rule_removes_existing_rule(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)
    service.set_rule(portfolio_id, dimension_type="currency", dimension_key="USD")

    deleted = service.delete_rule(portfolio_id, "currency", "USD")
    assert deleted is True
    assert service.list_rules(portfolio_id) == []


def test_delete_rule_returns_false_when_not_found(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    assert service.delete_rule(portfolio_id, "class", "fii") is False


def test_dimensions_are_independent_same_key_different_dimension(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = TargetAllocationRuleService(db_session)

    service.set_rule(portfolio_id, dimension_type="class", dimension_key="US", priority=1)
    service.set_rule(portfolio_id, dimension_type="country", dimension_key="US", priority=2)

    rules = service.list_rules(portfolio_id)
    assert len(rules) == 2


def test_repository_get_returns_none_when_not_found(db_session):
    portfolio_id = _seed_portfolio(db_session)
    repo = TargetAllocationRuleRepository(db_session)
    assert repo.get(portfolio_id, "class", "fii") is None
