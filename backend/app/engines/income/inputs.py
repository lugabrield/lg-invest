"""Contrato de entrada e configuração do Income Engine (Sprint 24, Fase 7).

A engine é pura: não acessa banco nem rede. O `IncomeAnalysisService`
resolve os eventos/agregados de `income_events` e `income_monthly_summaries`
(já convertidos para a moeda base), os custos de aquisição das posições, e
entrega esta estrutura pronta.

Duas fontes de proventos convivem no banco (Sprint 23), com semânticas
diferentes, e a engine **nunca as soma entre si**:
- `monthly_totals`: agregado mensal por carteira/fonte (aba "Análise" do
  Dividendos.me) — sem ticker, usado só para tendência/projeção
  agregada da carteira inteira.
- `ticker_events`: eventos individuais por ativo (calendário de
  proventos) — usados só para renda por ativo, yield on cost e
  concentração de renda.
Somar as duas arriscaria contar o mesmo provento duas vezes (uma fonte
agregada, outra granular) — ver `docs/INCOME_ENGINE.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class MonthlyIncomeTotal:
    """Um mês de renda agregada por carteira (fonte: "Análise"), já
    convertido para a moeda base. Pode haver mais de uma linha para o
    mesmo (year, month) se houver mais de uma carteira/fonte — a engine
    soma essas linhas (mesma origem de dado, não é mistura de fontes)."""

    year: int
    month: int  # 1..12
    amount_total: Decimal


@dataclass(frozen=True)
class TickerIncomeEvent:
    """Um provento individual recebido por um ativo específico, já
    convertido para a moeda base."""

    ticker: str
    payment_date: date
    amount_total: Decimal


@dataclass(frozen=True)
class IncomeEngineInput:
    reference_date: date
    monthly_totals: tuple[MonthlyIncomeTotal, ...] = ()
    ticker_events: tuple[TickerIncomeEvent, ...] = ()
    position_cost_basis: dict[str, Decimal] = field(
        default_factory=dict
    )  # ticker -> quantidade * preço médio, moeda base


@dataclass(frozen=True)
class IncomeConfig:
    months_lookback: int = 24  # janela total analisada (TTM atual + TTM anterior)
    projection_months: int = 12


DEFAULT_CONFIG = IncomeConfig()
