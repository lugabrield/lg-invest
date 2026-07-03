"""Schema de saída do Target Allocation Engine (Sprint 17 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

# "abaixo": alocação atual abaixo da meta (candidato a aporte);
# "dentro": dentro da tolerância; "acima": acima da meta (candidato a
# reduzir/pausar aportes nessa classe).
DRIFT_STATUSES = ("abaixo", "dentro", "acima")


class AllocationClassDrift(BaseModel):
    asset_class: str
    current_pct: Decimal  # fração 0..1
    target_pct: Decimal  # fração 0..1
    drift_pct: Decimal  # current_pct - target_pct (pode ser negativo)
    status: str  # ver DRIFT_STATUSES


class TargetAllocationResult(BaseModel):
    """Comparação entre alocação atual e alocação-alvo, por classe."""

    has_target: bool = False
    classes: list[AllocationClassDrift] = []
    most_underweight_class: str | None = None  # maior "abaixo" — candidato a próximo aporte
    reason: str | None = None  # ex.: "nenhuma meta de alocação configurada"
