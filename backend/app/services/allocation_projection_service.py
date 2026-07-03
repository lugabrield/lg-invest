"""Projeção de alocação antes/depois de um aporte (Sprint 11).

Não altera o Decision Engine: recebe o `DashboardView` (posições atuais
já convertidas) e o `RecommendationResult` que o Decision Engine já
calculou, e só explica como os pesos por classe/grupo e por moeda
mudariam se a recomendação fosse aplicada integralmente.

`build_allocation_projection` é uma função pura (sem `db`, sem efeito
colateral): recebe os dois objetos já prontos e devolve a projeção.
Isso só é possível porque o Decision Engine (`decision_service.py`)
constrói seus candidatos a partir das posições já existentes na
carteira — ou seja, todo ticker recomendado já aparece em
`view.positions`, e nenhuma consulta adicional ao banco é necessária
aqui.

Simplificação assumida: o valor do aporte é tratado como um montante em
BRL somado ao valor já convertido de cada posição recomendada — esta
projeção não simula a compra em moeda estrangeira nem custos de câmbio.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.allocation_projection import AllocationProjection, WeightComparison
from backend.app.schemas.dashboard_view import DashboardView
from backend.app.schemas.recommendation_result import RecommendationResult

_ZERO = Decimal("0")


def _weighted(values: dict[str, Decimal], total: Decimal) -> dict[str, Decimal]:
    if total <= 0:
        return dict.fromkeys(values, _ZERO)
    return {label: value / total for label, value in values.items()}


def _to_comparisons(
    before_values: dict[str, Decimal],
    after_values: dict[str, Decimal],
    total_before: Decimal,
    total_after: Decimal,
) -> list[WeightComparison]:
    before_weights = _weighted(before_values, total_before)
    after_weights = _weighted(after_values, total_after)
    labels = sorted(
        set(before_values) | set(after_values),
        key=lambda label: after_weights.get(label, _ZERO),
        reverse=True,
    )
    return [
        WeightComparison(
            label=label,
            weight_before=before_weights.get(label, _ZERO),
            weight_after=after_weights.get(label, _ZERO),
        )
        for label in labels
    ]


def build_allocation_projection(
    view: DashboardView, recommendation: RecommendationResult
) -> AllocationProjection:
    """Calcula os pesos por grupo e por moeda antes e depois do aporte simulado."""
    amount_by_ticker: dict[str, Decimal] = {
        item.ticker: item.amount for item in recommendation.items
    }

    value_before: dict[str, Decimal] = {p.ticker: p.position_value_brl for p in view.positions}
    value_after: dict[str, Decimal] = {
        ticker: value + amount_by_ticker.get(ticker, _ZERO)
        for ticker, value in value_before.items()
    }

    total_before = view.total_converted_brl
    total_after = total_before + recommendation.allocated_amount

    group_before: dict[str, Decimal] = {}
    group_after: dict[str, Decimal] = {}
    currency_before: dict[str, Decimal] = {}
    currency_after: dict[str, Decimal] = {}
    for p in view.positions:
        group_before[p.group_label] = (
            group_before.get(p.group_label, _ZERO) + value_before[p.ticker]
        )
        group_after[p.group_label] = group_after.get(p.group_label, _ZERO) + value_after[p.ticker]
        currency_before[p.currency] = (
            currency_before.get(p.currency, _ZERO) + value_before[p.ticker]
        )
        currency_after[p.currency] = currency_after.get(p.currency, _ZERO) + value_after[p.ticker]

    return AllocationProjection(
        contribution_amount=recommendation.contribution_amount,
        total_before_brl=total_before,
        total_after_brl=total_after,
        by_group=_to_comparisons(group_before, group_after, total_before, total_after),
        by_currency=_to_comparisons(currency_before, currency_after, total_before, total_after),
    )
