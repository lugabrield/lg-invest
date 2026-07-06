"""Testes do Monte Carlo Simulation Engine (Sprint 24, Fase 5) — engine pura,
sem banco."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.simulation.engine import run_simulation
from backend.app.engines.simulation.inputs import (
    ClassAssumption,
    SimulationConfig,
    SimulationInput,
)


def _data(**overrides) -> SimulationInput:
    base = dict(
        initial_value=Decimal("100000"),
        monthly_contribution=Decimal("1000"),
        horizon_years=20,
        class_weights={"stock": Decimal("1")},
        class_assumptions={
            "stock": ClassAssumption("stock", Decimal("0.10"), Decimal("0.20")),
        },
    )
    base.update(overrides)
    return SimulationInput(**base)


def test_percentiles_are_ordered():
    result = run_simulation(_data(), SimulationConfig(num_simulations=1000, random_seed=1))
    values = [result.percentiles[f"p{p}"] for p in (10, 25, 50, 75, 90)]
    assert values == sorted(values)


def test_deterministic_with_same_seed():
    config = SimulationConfig(num_simulations=500, random_seed=7)
    r1 = run_simulation(_data(), config)
    r2 = run_simulation(_data(), config)
    assert r1.percentiles == r2.percentiles
    assert r1.median_final_value == r2.median_final_value


def test_zero_volatility_matches_analytic_compound_growth():
    data = _data(
        class_assumptions={"stock": ClassAssumption("stock", Decimal("0.10"), Decimal("0"))},
        monthly_contribution=Decimal("0"),
    )
    result = run_simulation(data, SimulationConfig(num_simulations=50, random_seed=3))
    expected = float(data.initial_value) * (1.10**data.horizon_years)
    assert abs(float(result.median_final_value) - expected) < 1.0
    assert result.probability_of_loss == Decimal("0")


def test_higher_monthly_contribution_increases_median():
    config = SimulationConfig(num_simulations=1500, random_seed=11)
    low = run_simulation(_data(monthly_contribution=Decimal("100")), config)
    high = run_simulation(_data(monthly_contribution=Decimal("5000")), config)
    assert high.median_final_value > low.median_final_value


def test_longer_horizon_increases_median_with_positive_return():
    config = SimulationConfig(num_simulations=1500, random_seed=13)
    short = run_simulation(_data(horizon_years=5), config)
    long = run_simulation(_data(horizon_years=30), config)
    assert long.median_final_value > short.median_final_value


def test_zero_horizon_returns_initial_value_without_projection():
    result = run_simulation(_data(horizon_years=0), SimulationConfig(num_simulations=100))
    assert result.median_final_value == Decimal("100000")
    assert result.num_simulations == 0
    assert any("zerado" in w for w in result.warnings)


def test_missing_assumption_for_weighted_class_warns_and_treats_as_zero_return():
    data = _data(
        class_weights={"stock": Decimal("0.5"), "crypto": Decimal("0.5")},
        class_assumptions={"stock": ClassAssumption("stock", Decimal("0.10"), Decimal("0.0"))},
    )
    result = run_simulation(data, SimulationConfig(num_simulations=200, random_seed=5))
    assert any("crypto" in w for w in result.warnings)


def test_total_contributed_accounts_for_initial_and_monthly_contributions():
    data = _data(monthly_contribution=Decimal("1000"), horizon_years=10)
    result = run_simulation(data, SimulationConfig(num_simulations=10, random_seed=2))
    assert result.total_contributed == Decimal("100000") + Decimal("1000") * 12 * 10


def test_reasons_document_assumptions_used_and_disclaim_projection():
    result = run_simulation(_data(), SimulationConfig(num_simulations=10, random_seed=2))
    all_reasons = " ".join(result.reasons)
    assert "stock" in all_reasons
    assert "projeção probabilística" in all_reasons


def test_no_assumptions_at_all_only_accumulates_contributions():
    data = _data(class_weights={}, class_assumptions={})
    result = run_simulation(data, SimulationConfig(num_simulations=10, random_seed=2))
    expected = (
        float(data.initial_value) + float(data.monthly_contribution) * 12 * data.horizon_years
    )
    assert abs(float(result.median_final_value) - expected) < 1.0
