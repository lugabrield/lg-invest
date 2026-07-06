"""Monte Carlo Simulation Engine (Sprint 24, Fase 5).

Projeta trajetórias possíveis do valor futuro da carteira, dado o valor
atual, um aporte mensal presumido e premissas de retorno/volatilidade
anual por classe de ativo. A engine roda `config.num_simulations`
trajetórias independentes e resume o resultado em percentis — nunca em um
único número "previsto".

Isto é uma ferramenta de projeção probabilística, não uma previsão real de
mercado nem uma recomendação financeira. As premissas de retorno/
volatilidade são sempre explícitas e editáveis pelo usuário (nunca
inventadas silenciosamente pela engine) — ver `docs/SIMULATION_ENGINE.md`
para o disclaimer completo e a metodologia.

Simplificações assumidas deliberadamente (sempre documentadas em
`reasons`/`warnings` do resultado, nunca escondidas):
- Retornos anuais são amostrados de uma normal (não log-normal) por
  classe, de forma independente entre classes (sem correlação entre
  classes de ativo — ex.: ações BR e ações US podem cair juntas na
  realidade, o modelo não captura isso).
- O retorno anual de cada trajetória é limitado a um piso de -95% (evita
  valores negativos de patrimônio em uma única amostragem extrema).
- Aportes mensais são aplicados de uma vez ao final de cada ano (não
  mês a mês) — simplificação para viabilizar `num_simulations` altos.
- A composição por classe da carteira é mantida fixa ao longo de todo o
  horizonte (sem rebalanceamento simulado).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from backend.app.engines.simulation.inputs import (
    DEFAULT_CONFIG,
    SimulationConfig,
    SimulationInput,
)

MODEL_VERSION = "simulation_v1"

_RETURN_FLOOR = -0.95  # piso de retorno anual por trajetória (evita patrimônio negativo)


@dataclass
class SimulationResult:
    model_version: str
    initial_value: Decimal
    monthly_contribution: Decimal
    horizon_years: int
    num_simulations: int
    total_contributed: Decimal  # initial_value + monthly_contribution * 12 * horizon_years
    percentiles: dict[str, Decimal]  # ex.: {"p10": ..., "p50": ..., "p90": ...}
    median_final_value: Decimal
    probability_of_loss: Decimal  # fração de trajetórias que terminam abaixo do total aportado
    reasons: list[str]
    warnings: list[str]


def run_simulation(
    data: SimulationInput,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> SimulationResult:
    """Roda a simulação de Monte Carlo pura (sem banco/rede)."""
    reasons: list[str] = []
    warnings: list[str] = []

    total_contributed = data.initial_value + (
        data.monthly_contribution * Decimal("12") * Decimal(data.horizon_years)
    )

    classes_with_weight = {c for c, w in data.class_weights.items() if w > 0}
    classes_with_assumption = set(data.class_assumptions.keys())
    missing_assumptions = classes_with_weight - classes_with_assumption
    if missing_assumptions:
        warnings.append(
            "sem premissa de retorno/volatilidade configurada para as classes "
            f"{sorted(missing_assumptions)} — tratadas como retorno 0% (nem ganho "
            "nem perda) nesta simulação, não é uma previsão de retorno real."
        )

    for asset_class, assumption in sorted(data.class_assumptions.items()):
        weight = data.class_weights.get(asset_class, Decimal("0"))
        if weight <= 0:
            continue
        reasons.append(
            f"classe '{asset_class}' (peso {weight * 100:.1f}%): retorno esperado "
            f"{assumption.expected_return * 100:.1f}%/ano, volatilidade "
            f"{assumption.volatility * 100:.1f}%/ano ({assumption.source})."
        )

    reasons.append(
        "simulação com retornos anuais normais e independentes por classe (sem "
        "correlação entre classes), aportes aplicados ao final de cada ano, "
        "composição da carteira mantida fixa ao longo do horizonte — "
        "projeção probabilística, não uma previsão de mercado real."
    )

    if data.horizon_years <= 0 or config.num_simulations <= 0:
        final_value = data.initial_value
        percentiles = {f"p{p}": final_value for p in config.percentiles}
        warnings.append(
            "horizonte de simulação zerado ou número de simulações inválido — "
            "resultado é apenas o valor atual da carteira, sem projeção."
        )
        return SimulationResult(
            model_version=MODEL_VERSION,
            initial_value=data.initial_value,
            monthly_contribution=data.monthly_contribution,
            horizon_years=data.horizon_years,
            num_simulations=0,
            total_contributed=total_contributed,
            percentiles=percentiles,
            median_final_value=final_value,
            probability_of_loss=Decimal("0"),
            reasons=reasons,
            warnings=warnings,
        )

    rng = np.random.default_rng(config.random_seed)

    weights = np.array(
        [float(data.class_weights.get(c, Decimal("0"))) for c in sorted(classes_with_assumption)]
    )
    means = np.array(
        [float(data.class_assumptions[c].expected_return) for c in sorted(classes_with_assumption)]
    )
    vols = np.array(
        [float(data.class_assumptions[c].volatility) for c in sorted(classes_with_assumption)]
    )

    initial = float(data.initial_value)
    annual_contribution = float(data.monthly_contribution) * 12.0

    final_values = np.empty(config.num_simulations)

    if weights.size == 0:
        # Nenhuma classe com premissa configurada: sem componente de mercado,
        # só acumula os aportes (nunca inventa um retorno).
        final = initial + annual_contribution * data.horizon_years
        final_values[:] = final
    else:
        for i in range(config.num_simulations):
            value = initial
            for _year in range(data.horizon_years):
                class_returns = rng.normal(loc=means, scale=vols)
                class_returns = np.maximum(class_returns, _RETURN_FLOOR)
                portfolio_return = float(np.dot(weights, class_returns))
                portfolio_return = max(portfolio_return, _RETURN_FLOOR)
                value = value * (1 + portfolio_return) + annual_contribution
            final_values[i] = value

    percentiles = {
        f"p{p}": Decimal(str(round(float(np.percentile(final_values, p)), 2)))
        for p in config.percentiles
    }
    median_final_value = Decimal(str(round(float(np.median(final_values)), 2)))
    probability_of_loss = Decimal(
        str(round(float(np.mean(final_values < float(total_contributed))), 4))
    )

    return SimulationResult(
        model_version=MODEL_VERSION,
        initial_value=data.initial_value,
        monthly_contribution=data.monthly_contribution,
        horizon_years=data.horizon_years,
        num_simulations=config.num_simulations,
        total_contributed=total_contributed,
        percentiles=percentiles,
        median_final_value=median_final_value,
        probability_of_loss=probability_of_loss,
        reasons=reasons,
        warnings=warnings,
    )
