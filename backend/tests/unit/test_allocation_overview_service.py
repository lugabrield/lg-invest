"""Testes de `allocation_overview_service.py` (ajuste UX Configurações/alocação).

Cobre só a orquestração (leitura de regras/política/alocação simples e
delegação para `engines/target_allocation/precedence.py`) — a lógica de
precedência/conflito em si já é testada isoladamente em
`test_target_allocation_precedence.py`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Portfolio
from backend.app.services import target_allocation_settings_service as simple_settings
from backend.app.services.allocation_overview_service import build_allocation_overview
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    # Mesma isolação de `test_target_allocation_settings_service.py` — evita
    # gravar no `data/app_settings.json` real durante os testes.
    monkeypatch.setattr(simple_settings, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.commit()
    return portfolio.id


def test_overview_uses_policy_fallback_when_no_detailed_rule(db_session):
    portfolio_id = _seed_portfolio(db_session)

    overview = build_allocation_overview(db_session, portfolio_id)

    fii = next(
        el
        for el in overview.effective_limits
        if el.dimension_type == "class" and el.dimension_key == "fii"
    )
    assert fii.source == "politica_geral"


def test_overview_reflects_detailed_rule_override(db_session):
    portfolio_id = _seed_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        max_weight=Decimal("0.30"),
    )

    overview = build_allocation_overview(db_session, portfolio_id)

    fii = next(
        el
        for el in overview.effective_limits
        if el.dimension_type == "class" and el.dimension_key == "fii"
    )
    assert fii.source == "regra_detalhada"
    assert fii.max_weight == Decimal("0.30")


def test_overview_detects_conflict_between_simple_and_detailed(db_session):
    portfolio_id = _seed_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id,
        dimension_type="class",
        dimension_key="fii",
        target_weight=Decimal("0.25"),
    )
    simple_settings.set_target_allocation(
        {
            "fii": Decimal("0.15"),
            "stock": Decimal("0.85"),
        }
    )

    overview = build_allocation_overview(db_session, portfolio_id)
    assert any(c.kind == "simple_vs_detailed" for c in overview.conflicts)


def test_overview_has_no_conflicts_by_default(db_session):
    portfolio_id = _seed_portfolio(db_session)
    overview = build_allocation_overview(db_session, portfolio_id)
    assert overview.conflicts == []
