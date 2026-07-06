"""Contrato de entrada e configuração do Monte Carlo Simulation Engine
(Sprint 24, Fase 5).

A engine é pura: não acessa banco nem rede, não busca cotações e não sabe
o que é um `Portfolio`. O serviço (`SimulationService`) resolve o valor
atual da carteira, os pesos por classe e as premissas de retorno/
volatilidade, e entrega esta estrutura pronta para a engine.

Nenhuma premissa de retorno/volatilidade é inventada pela engine — elas
sempre vêm de fora (`ClassAssumption`, resolvidas pelo
`SimulationAssumptionsService`, com defaults explícitos e editáveis pelo
usuário, nunca escondidos). Ver `docs/SIMULATION_ENGINE.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ClassAssumption:
    """Premissa de retorno/volatilidade anual para uma classe de ativo.

    Estas são sempre premissas de longo prazo configuráveis pelo usuário
    (Buy and Hold, horizonte 50+ anos) — nunca uma previsão real de
    mercado. `source` documenta de onde veio o valor (ex.: "default do
    sistema" ou "ajustado pelo usuário"), nunca deixando isso implícito.
    """

    asset_class: str
    expected_return: Decimal  # retorno médio anual esperado, fração (ex.: 0.11 = 11%)
    volatility: Decimal  # desvio padrão anual esperado, fração (ex.: 0.22 = 22%)
    source: str = "default do sistema"


@dataclass(frozen=True)
class SimulationInput:
    """Estado atual da carteira + premissas, pronto para a simulação."""

    initial_value: Decimal  # valor atual total da carteira (moeda base)
    monthly_contribution: Decimal  # aporte mensal presumido, constante ao longo do horizonte
    horizon_years: int
    class_weights: dict[str, Decimal] = field(default_factory=dict)  # fração 0..1, soma ~1
    class_assumptions: dict[str, ClassAssumption] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationConfig:
    """Parâmetros do método Monte Carlo em si (não da carteira)."""

    num_simulations: int = 2000
    random_seed: int | None = None  # fixo em testes para reprodutibilidade; None = aleatório real
    percentiles: tuple[int, ...] = (10, 25, 50, 75, 90)


DEFAULT_CONFIG = SimulationConfig()
