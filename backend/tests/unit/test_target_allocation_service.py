"""Testes do TargetAllocationService (wiring Portfolio Engine -> config -> engine)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services import target_allocation_settings_service as settings_svc
from backend.app.services.target_allocation_service import TargetAllocationService


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


def test_no_target_configured(db_session):
    portfolio_id = _seed_portfolio(db_session)
    result = TargetAllocationService(db_session).evaluate_portfolio(portfolio_id)
    assert result.has_target is False


def test_drift_computed_against_configured_target(db_session):
    portfolio_id = _seed_portfolio(db_session)
    # WEGE3: 100*40=4000; HGLG11: 50*100=5000; total=9000
    # stock = 44.4%, fii = 55.6%
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

    result = TargetAllocationService(db_session).evaluate_portfolio(portfolio_id)

    assert result.has_target is True
    stock_drift = next(c for c in result.classes if c.asset_class == "stock")
    assert stock_drift.status == "abaixo"
    fii_drift = next(c for c in result.classes if c.asset_class == "fii")
    assert fii_drift.status == "acima"
