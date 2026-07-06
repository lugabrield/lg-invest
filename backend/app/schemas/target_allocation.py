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


# --- Target Allocation Engine v2 (Sprint 24, Fase 3) -------------------------
#
# Generaliza a comparação para 4 dimensões independentes (classe, moeda,
# país, ativo individual), com peso mínimo/alvo/máximo e prioridade de
# aporte manual — usa `TargetAllocationRule` (tabela) em vez do JSON de
# classe-only da Sprint 17. `TargetAllocationResult`/`AllocationClassDrift`
# acima continuam existindo e em uso (Decision Engine 2.0, Dashboard) —
# esta v2 é aditiva, não substitui a v1.

# "underweight": abaixo do alvo, candidato a aporte; "neutral": dentro da
# tolerância (rebalance_threshold); "overweight": acima do alvo mas ainda
# dentro do peso máximo (se houver) — não aportar mais, nunca vender
# automaticamente; "blocked": ultrapassou o peso MÁXIMO configurado — aporte
# bloqueado nessa dimensão (ver Decision Engine 3.0, Fase 4).
GAP_STATUSES = ("underweight", "neutral", "overweight", "blocked")


class AllocationRuleEvaluation(BaseModel):
    """Avaliação de UMA regra (uma dimensão/chave) — ex.: dimension_type
    "class", dimension_key "fii"."""

    dimension_type: str  # ver TARGET_ALLOCATION_DIMENSIONS
    dimension_key: str

    current_weight: Decimal
    target_weight: Decimal | None = None
    min_weight: Decimal | None = None
    max_weight: Decimal | None = None

    gap_to_target: Decimal | None = None  # current_weight - target_weight (None se sem alvo)
    gap_status: str  # ver GAP_STATUSES
    contribution_priority: (
        int  # maior = mais prioritário para o próximo aporte; <=0 = não priorizar
    )
    rebalance_required: bool  # true quando o desvio ultrapassa o rebalance_threshold
    extreme_overweight: bool = False  # current_weight > max_weight * 1.5 (ver docstring do engine)
    alert_message: str | None = None


class TargetAllocationEvaluation(BaseModel):
    """Resultado agregado da avaliação por regras — agrupado por dimensão
    para a UI conseguir renderizar seções separadas (classe/moeda/país/ativo)."""

    has_rules: bool = False
    evaluations: list[AllocationRuleEvaluation] = []
    reason: str | None = None  # ex.: "nenhuma regra de alocação configurada"

    def by_dimension(self, dimension_type: str) -> list[AllocationRuleEvaluation]:
        return [e for e in self.evaluations if e.dimension_type == dimension_type]
