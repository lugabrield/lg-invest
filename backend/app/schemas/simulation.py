"""Schemas do Monte Carlo Simulation Engine (Sprint 24, Fase 5)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class ClassAssumptionView(BaseModel):
    """Premissa de retorno/volatilidade anual em uso para uma classe."""

    asset_class: str
    expected_return: Decimal  # fração anual, ex.: 0.11 = 11%
    volatility: Decimal  # fração anual, ex.: 0.22 = 22%
    source: str  # "default do sistema" | "ajustado pelo usuário" | ...


class SimulationAssumptionsView(BaseModel):
    """Todas as premissas em uso (uma por classe suportada) + disclaimer."""

    assumptions: list[ClassAssumptionView]
    disclaimer: str


class SimulationAssumptionUpdate(BaseModel):
    """Payload para customizar a premissa de uma classe."""

    asset_class: str
    expected_return: Decimal
    volatility: Decimal


class SimulationResultView(BaseModel):
    """Resultado de uma simulação Monte Carlo, pronto para exibição."""

    model_version: str
    initial_value: Decimal
    monthly_contribution: Decimal
    horizon_years: int
    num_simulations: int
    total_contributed: Decimal
    percentiles: dict[str, Decimal]
    median_final_value: Decimal
    probability_of_loss: Decimal
    reasons: list[str]
    warnings: list[str]

    model_config = {"from_attributes": True}
