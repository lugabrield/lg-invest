"""Contrato de entrada e configuração do Portfolio Health Score
(Sprint 24, Fase 8) — o "capstone" que resume, num único score, sinais já
produzidos por outras engines/serviços da plataforma (Portfolio Engine,
Portfolio Risk Engine, Target Allocation Rule Engine v2, Income Engine,
Data Quality Layer).

A engine é pura: não acessa banco nem rede, e não importa nenhuma
engine/serviço alheio — o `PortfolioHealthService` resolve os 5 sinais
abaixo (cada um vindo de um serviço já existente) e entrega esta
estrutura pronta. Isso mantém a regra "engines continuam puras" mesmo
sendo, por natureza, uma agregação de outras análises.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AllocationAlignmentInput:
    """Quantas dimensões da alocação-alvo (Target Allocation Rule Engine
    v2) estão alinhadas (neutral/underweight) vs. não alinhadas
    (overweight/blocked)."""

    has_rules: bool
    total_evaluations: int
    aligned_evaluations: int  # gap_status em ("neutral", "underweight")


@dataclass(frozen=True)
class PortfolioHealthInput:
    effective_number_of_assets: Decimal | None  # Portfolio Engine (1/HHI)
    risk_overall_classification: str | None  # Portfolio Risk Engine (Fase 6)
    declared_risk_tolerance: str | None  # Investment Policy (Fase 3)
    allocation_alignment: AllocationAlignmentInput | None  # Target Allocation Rule Engine v2
    income_growth_pct: Decimal | None  # Income Engine (Fase 7), PortfolioIncomeTrend.growth_pct
    data_confidence_pct: Decimal | None  # Data Quality Layer (Sprint 21), fração 0..1


@dataclass(frozen=True)
class PortfolioHealthConfig:
    """Pesos dos 5 pilares (somam 1.0). Pilar indisponível tem seu peso
    renormalizado entre os demais — nunca inventado."""

    weight_diversification: Decimal = Decimal("0.25")
    weight_risk_alignment: Decimal = Decimal("0.25")
    weight_allocation_alignment: Decimal = Decimal("0.20")
    weight_income_trend: Decimal = Decimal("0.15")
    weight_data_confidence: Decimal = Decimal("0.15")


DEFAULT_CONFIG = PortfolioHealthConfig()
