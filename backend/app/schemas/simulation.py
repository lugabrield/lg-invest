"""Schemas do Monte Carlo Simulation Engine (Sprint 24, Fase 5)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator


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


class SimulationRunRequest(BaseModel):
    """Payload para rodar uma simulação (v1.1, Fase 8).

    Mesmos limites de `pages_impl/simulacao.py` (`st.number_input`
    min/max/value): aporte mensal >= 0, horizonte 1-100 anos, nº de
    simulações 100-20000. `reproducible` espelha o checkbox "Usar
    semente fixa" — quando marcado, a rota usa a mesma seed 42 fixa do
    Streamlit (não um valor arbitrário do cliente), para manter o
    mesmo comportamento observável.
    """

    monthly_contribution: Decimal = Decimal("1000")
    horizon_years: int = 20
    num_simulations: int = 2000
    reproducible: bool = False

    @field_validator("monthly_contribution")
    @classmethod
    def contribution_not_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("monthly_contribution não pode ser negativo.")
        return value

    @field_validator("horizon_years")
    @classmethod
    def horizon_in_range(cls, value: int) -> int:
        if not (1 <= value <= 100):
            raise ValueError("horizon_years deve estar entre 1 e 100.")
        return value

    @field_validator("num_simulations")
    @classmethod
    def num_simulations_in_range(cls, value: int) -> int:
        if not (100 <= value <= 20000):
            raise ValueError("num_simulations deve estar entre 100 e 20000.")
        return value
