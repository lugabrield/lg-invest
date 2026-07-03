"""Testes do DecisionService v2 (Sprint 18) — wiring DB -> engines -> Decision Engine 2.0."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.services import target_allocation_settings_service as settings_svc
from backend.app.services.decision_service import DecisionService


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_svc, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def _seed_portfolio(db) -> tuple[int, int]:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    fii = Asset(
        ticker="HGLG11.SA", name="CSHG Logística", asset_class="fii", country="BR", currency="BRL"
    )
    db.add_all([stock, fii])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("100"),
                average_price=Decimal("38"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=fii.id,
                quantity=Decimal("50"),
                average_price=Decimal("100"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.add(Price(asset_id=fii.id, date=date(2026, 6, 27), close=Decimal("100")))
    db.commit()
    return portfolio.id, stock.id


def test_build_inputs_v2_uses_conviction_score_when_fundamentals_exist(db_session):
    portfolio_id, stock_id = _seed_portfolio(db_session)
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=stock_id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.20"),
            net_margin=Decimal("0.20"),
            debt_to_ebitda=Decimal("1"),
        )
    )

    inputs = DecisionService(db_session).build_inputs_v2(portfolio_id)

    wege_input = next(i for i in inputs if i.ticker == "WEGE3.SA")
    assert wege_input.conviction_score is not None


def test_build_inputs_v2_falls_back_without_fundamentals(db_session):
    portfolio_id, _ = _seed_portfolio(db_session)
    inputs = DecisionService(db_session).build_inputs_v2(portfolio_id)
    # Sem fundamentos coletados, o Conviction Score ainda é calculável
    # (cai para a proxy de preço em cada pilar) — não deve ser None.
    for candidate in inputs:
        assert candidate.conviction_score is not None


def test_build_inputs_v2_uses_class_drift_when_target_configured(db_session):
    portfolio_id, _ = _seed_portfolio(db_session)
    settings_svc.set_target_allocation(
        {
            "stock": Decimal("0.60"),
            "fii": Decimal("0.20"),
            "etf": Decimal("0.10"),
            "reit": Decimal("0.05"),
            "crypto": Decimal("0.02"),
            "bond": Decimal("0.02"),
            "cash": Decimal("0.01"),
        }
    )

    inputs = DecisionService(db_session).build_inputs_v2(portfolio_id)

    stock_input = next(i for i in inputs if i.ticker == "WEGE3.SA")
    assert stock_input.class_drift_pct is not None


def test_build_inputs_v2_no_drift_without_target(db_session):
    portfolio_id, _ = _seed_portfolio(db_session)
    inputs = DecisionService(db_session).build_inputs_v2(portfolio_id)
    for candidate in inputs:
        assert candidate.class_drift_pct is None


def test_recommend_v2_end_to_end(db_session):
    portfolio_id, _ = _seed_portfolio(db_session)
    result = DecisionService(db_session).recommend_v2(portfolio_id, Decimal("1000"), persist=False)
    assert result.audit.model_version == "decision_v2"
    total = sum((i.amount for i in result.items), start=Decimal("0"))
    assert total == result.allocated_amount
    assert total <= Decimal("1000")
