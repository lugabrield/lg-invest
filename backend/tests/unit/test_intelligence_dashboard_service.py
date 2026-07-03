"""Testes do serviço do painel de Inteligência (Sprint 19)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services import target_allocation_settings_service as settings_svc
from backend.app.services.intelligence_dashboard_service import build_intelligence_dashboard


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_svc, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def _seed_portfolio(db) -> int:
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
    return portfolio.id


def test_build_intelligence_dashboard_scores_every_position(db_session):
    portfolio_id = _seed_portfolio(db_session)

    view = build_intelligence_dashboard(db_session, portfolio_id)

    assert len(view.assets) == 2
    tickers = {a.ticker for a in view.assets}
    assert tickers == {"WEGE3.SA", "HGLG11.SA"}
    # Sem fundamentos coletados, o Conviction Score ainda é calculável via
    # fallback de preço em cada pilar (graceful degradation) — nunca None.
    for asset in view.assets:
        assert asset.has_conviction_score is True
        assert asset.conviction_score is not None
        assert asset.unavailable_reason is None


def test_build_intelligence_dashboard_aggregates_average_and_coverage(db_session):
    portfolio_id = _seed_portfolio(db_session)

    view = build_intelligence_dashboard(db_session, portfolio_id)

    assert view.average_conviction_score is not None
    assert Decimal("0") <= view.coverage_pct <= Decimal("1")
    assert view.most_convicted is not None
    assert view.least_convicted is not None
    assert sum(view.classification_counts.values()) == len(view.assets)


def test_build_intelligence_dashboard_without_target_allocation(db_session):
    portfolio_id = _seed_portfolio(db_session)

    view = build_intelligence_dashboard(db_session, portfolio_id)

    assert view.allocation_drift.has_target is False
    assert view.allocation_drift.classes == []


def test_build_intelligence_dashboard_with_target_allocation(db_session):
    portfolio_id = _seed_portfolio(db_session)
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

    view = build_intelligence_dashboard(db_session, portfolio_id)

    assert view.allocation_drift.has_target is True
    assert len(view.allocation_drift.classes) > 0


def test_build_intelligence_dashboard_empty_portfolio(db_session):
    portfolio = Portfolio(name="Vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()

    view = build_intelligence_dashboard(db_session, portfolio.id)

    assert view.assets == []
    assert view.average_conviction_score is None
    assert view.coverage_pct == Decimal("0")
    assert view.most_convicted is None
    assert view.least_convicted is None
