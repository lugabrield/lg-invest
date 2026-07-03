"""Schemas da projeção de alocação antes/depois de um aporte (Sprint 11).

Saída de `allocation_projection_service`: como os pesos por classe e por
moeda mudam se a recomendação do Decision Engine (inalterado) for
aplicada. É apresentação/explicação, não uma nova regra de decisão.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class WeightComparison(BaseModel):
    """Peso de um grupo (classe ou moeda) antes e depois do aporte."""

    label: str
    weight_before: Decimal  # fração 0..1
    weight_after: Decimal  # fração 0..1

    @property
    def delta(self) -> Decimal:
        return self.weight_after - self.weight_before

    model_config = {"from_attributes": True}


class AllocationProjection(BaseModel):
    """Projeção completa: totais e pesos antes/depois do aporte simulado."""

    contribution_amount: Decimal
    total_before_brl: Decimal
    total_after_brl: Decimal

    by_group: list[WeightComparison]  # classe/grupo (Ações BR, FIIs, ...), pesos antes e depois
    by_currency: list[WeightComparison]  # BRL, USD, pesos antes e depois

    model_config = {"from_attributes": True}
