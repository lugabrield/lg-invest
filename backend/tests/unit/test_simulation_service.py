"""Testes do SimulationService (Sprint 24, Fase 5) — wiring DB -> Monte Carlo
Simulation Engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services import simulation_assumptions_service as assumptions_svc
from backend.app.services.simulation_service import SimulationService


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setattr(assumptions_svc, "_SETTINGS_PATH", settings_path)
    yield settings_path


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    bond = Asset(
        ticker="TESOURO-IPCA",
        name="Tesouro IPCA+",
        asset_class="bond",
        country="BR",
        currency="BRL",
    )
    db.add_all([stock, bond])
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
                asset_id=bond.id,
                quantity=Decimal("1"),
                average_price=Decimal("6000"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.add(Price(asset_id=bond.id, date=date(2026, 6, 27), close=Decimal("6200")))
    db.commit()
    return portfolio.id


def test_build_input_reflects_current_portfolio_value_and_weights(db_session):
    portfolio_id = _seed_portfolio(db_session)
    data = SimulationService(db_session).build_input(
        portfolio_id, monthly_contribution=Decimal("500"), horizon_years=10
    )
    assert data.initial_value > Decimal("0")
    assert set(data.class_weights.keys()) == {"stock", "bond"}
    total_weight = sum(data.class_weights.values())
    assert abs(total_weight - Decimal("1")) < Decimal("0.0001")


def test_build_input_uses_configured_assumptions(db_session):
    portfolio_id = _seed_portfolio(db_session)
    assumptions_svc.set_assumption("stock", Decimal("0.14"), Decimal("0.30"))
    data = SimulationService(db_session).build_input(
        portfolio_id, monthly_contribution=Decimal("500"), horizon_years=10
    )
    assert data.class_assumptions["stock"].expected_return == Decimal("0.14")


def test_run_portfolio_simulation_end_to_end(db_session):
    portfolio_id = _seed_portfolio(db_session)
    result = SimulationService(db_session).run_portfolio_simulation(
        portfolio_id,
        monthly_contribution=Decimal("500"),
        horizon_years=15,
        num_simulations=300,
        seed=42,
    )
    assert result.model_version == "simulation_v1"
    assert result.num_simulations == 300
    assert result.percentiles["p10"] <= result.percentiles["p50"] <= result.percentiles["p90"]


def test_run_portfolio_simulation_handles_empty_portfolio(db_session):
    portfolio = Portfolio(name="Carteira vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()

    result = SimulationService(db_session).run_portfolio_simulation(
        portfolio.id,
        monthly_contribution=Decimal("500"),
        horizon_years=10,
        num_simulations=100,
        seed=1,
    )
    # Sem posições, sem peso por classe: só acumula os aportes futuros, sem
    # inventar um componente de mercado.
    expected = Decimal("500") * 12 * 10
    assert abs(result.median_final_value - expected) < Decimal("1")
