"""Resolução de precedência e detecção de conflitos entre as três camadas
de alocação-alvo (ajuste UX Configurações/alocação, pós-Sprint 25).

A LG INVEST tem três formas independentes de configurar meta de
alocação, criadas em sprints diferentes e nunca antes mostradas juntas
na tela:

1. Alocação-alvo SIMPLES por classe (Sprint 17) — um número por classe,
   guardado em JSON (`target_allocation_settings_service.py`).
2. Regras DETALHADAS por classe/moeda/país/ativo (Sprint 24) — tabela
   `target_allocation_rules`, com mínimo/alvo/máximo/prioridade por
   dimensão.
3. Política de investimento GERAL (Sprint 24) — parâmetros amplos
   (`InvestmentPolicy`): peso máximo por ativo, peso máximo em cripto,
   peso máximo em FIIs, entre outros.

O Decision Engine 3.0 (`engines/decision/eligibility.py::filter_eligible_v3`)
já usa uma precedência real entre (2) e (3) para BLOQUEAR aportes: regra
detalhada > política geral > nenhum limite. Este módulo replica a MESMA
precedência, mas só para EXIBIÇÃO na tela de Configurações — não decide
nada sozinho, não é chamado pelo Decision Engine, e não deve divergir da
lógica de bloqueio real (qualquer mudança lá deve ser espelhada aqui).

Puro: sem banco, rede ou Streamlit. Nunca recomenda venda — todo
"conflito" ou "limite excedido" aqui é só informativo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Classes de ativo cuja Investment Policy tem um campo de limite máximo
# dedicado, usado como FALLBACK quando não existe regra detalhada de
# classe com `max_weight` — mesma cobertura de `eligibility.py`
# (`max_crypto_weight`/`target_fii_max`). Outras classes (stock, etf,
# reit, bond, cash) não têm fallback de política hoje: sem regra
# detalhada, elas simplesmente não têm limite.
POLICY_CLASS_MAX_FIELDS = {
    "crypto": "max_crypto_weight",
    "fii": "target_fii_max",
}

_TOLERANCE = Decimal("0.001")

SOURCE_DETAILED_RULE = "regra_detalhada"
SOURCE_GENERAL_POLICY = "politica_geral"
EFFECTIVE_LIMIT_SOURCES = (SOURCE_DETAILED_RULE, SOURCE_GENERAL_POLICY)

CONFLICT_SIMPLE_VS_DETAILED = "simple_vs_detailed"
CONFLICT_SUM_NOT_100 = "sum_not_100"
CONFLICT_MIN_GREATER_THAN_TARGET = "min_greater_than_target"


@dataclass(frozen=True)
class RuleLike:
    """Entrada pura — espelha `TargetAllocationRule` (banco) sem depender
    do ORM, mesmo padrão de `AllocationRuleInput` em `engine.py`."""

    dimension_type: str
    dimension_key: str
    min_weight: Decimal | None
    target_weight: Decimal | None
    max_weight: Decimal | None
    priority: int = 0


@dataclass(frozen=True)
class PolicyLike:
    """Só os campos de `InvestmentPolicyView` usados aqui — evita este
    módulo puro depender do schema completo da política."""

    max_asset_weight: Decimal | None
    max_crypto_weight: Decimal | None
    target_fii_max: Decimal | None


@dataclass(frozen=True)
class EffectiveLimit:
    """Um limite máximo efetivo para exibição — de onde ele vem
    (`source`) é sempre explícito, nunca implícito."""

    dimension_type: str
    dimension_key: str
    max_weight: Decimal
    source: str  # ver EFFECTIVE_LIMIT_SOURCES
    overridden_policy_value: Decimal | None = None
    """Quando `source == SOURCE_DETAILED_RULE` e a política geral também
    tinha um valor para a mesma dimensão, o valor da política que foi
    sobrescrito — só para deixar visível que a regra detalhada "venceu"."""


@dataclass(frozen=True)
class AllocationConflict:
    kind: str  # CONFLICT_*
    message: str


def resolve_effective_limits(
    rules: list[RuleLike], policy: PolicyLike | None
) -> list[EffectiveLimit]:
    """Limite máximo efetivo por dimensão, com a mesma precedência do
    Decision Engine 3.0: regra detalhada > política geral > nenhum
    limite. Só gera uma linha por dimensão que TEM algum limite — nunca
    inventa um limite para uma dimensão sem regra nem política."""
    results: list[EffectiveLimit] = []
    rules_by_key = {(r.dimension_type, r.dimension_key): r for r in rules}

    # Ativo genérico: cada regra `asset` com max_weight é, por si só, o
    # limite efetivo daquele ticker específico (a política nunca a
    # sobrescreve — é o inverso). A política só aparece como uma linha
    # "genérica" para tickers que NÃO têm regra própria.
    asset_rules_with_max = [
        r for r in rules if r.dimension_type == "asset" and r.max_weight is not None
    ]
    for r in asset_rules_with_max:
        results.append(
            EffectiveLimit(
                dimension_type="asset",
                dimension_key=r.dimension_key,
                max_weight=r.max_weight,
                source=SOURCE_DETAILED_RULE,
                overridden_policy_value=(policy.max_asset_weight if policy is not None else None),
            )
        )
    if policy is not None and policy.max_asset_weight is not None:
        results.append(
            EffectiveLimit(
                dimension_type="asset",
                dimension_key="(qualquer ativo sem regra própria)",
                max_weight=policy.max_asset_weight,
                source=SOURCE_GENERAL_POLICY,
            )
        )

    # Classes com fallback de política (crypto, fii).
    for class_key, policy_field in POLICY_CLASS_MAX_FIELDS.items():
        rule = rules_by_key.get(("class", class_key))
        policy_value = getattr(policy, policy_field, None) if policy is not None else None
        if rule is not None and rule.max_weight is not None:
            results.append(
                EffectiveLimit(
                    dimension_type="class",
                    dimension_key=class_key,
                    max_weight=rule.max_weight,
                    source=SOURCE_DETAILED_RULE,
                    overridden_policy_value=policy_value,
                )
            )
        elif policy_value is not None:
            results.append(
                EffectiveLimit(
                    dimension_type="class",
                    dimension_key=class_key,
                    max_weight=policy_value,
                    source=SOURCE_GENERAL_POLICY,
                )
            )

    # Demais regras detalhadas com max_weight (sem fallback de política:
    # moeda, país, e classes fora de POLICY_CLASS_MAX_FIELDS) — sempre
    # "regra_detalhada" quando existem, sem equivalente na política.
    covered = {("class", key) for key in POLICY_CLASS_MAX_FIELDS} | {
        ("asset", r.dimension_key) for r in asset_rules_with_max
    }
    for r in rules:
        if r.max_weight is None:
            continue
        key = (r.dimension_type, r.dimension_key)
        if key in covered:
            continue
        results.append(
            EffectiveLimit(
                dimension_type=r.dimension_type,
                dimension_key=r.dimension_key,
                max_weight=r.max_weight,
                source=SOURCE_DETAILED_RULE,
            )
        )

    return results


def detect_conflicts(
    rules: list[RuleLike], simple_allocation: dict[str, Decimal]
) -> list[AllocationConflict]:
    """Conflitos informativos entre as camadas — nunca bloqueia nada,
    nunca corrige sozinho, só avisa o usuário para ele decidir."""
    conflicts: list[AllocationConflict] = []

    class_rules = {r.dimension_key: r for r in rules if r.dimension_type == "class"}
    for asset_class, simple_target in sorted(simple_allocation.items()):
        rule = class_rules.get(asset_class)
        if rule is None or rule.target_weight is None:
            continue
        if abs(rule.target_weight - simple_target) > _TOLERANCE:
            conflicts.append(
                AllocationConflict(
                    kind=CONFLICT_SIMPLE_VS_DETAILED,
                    message=(
                        f"Classe '{asset_class}': a meta simples ({simple_target * 100:.1f}%) "
                        f"é diferente do alvo da regra detalhada "
                        f"({rule.target_weight * 100:.1f}%). A regra detalhada tem "
                        "precedência — é ela que vale."
                    ),
                )
            )

    class_targets = [
        r.target_weight
        for r in rules
        if r.dimension_type == "class" and r.target_weight is not None
    ]
    if class_targets:
        total = sum(class_targets, Decimal("0"))
        if abs(total - Decimal("1")) > _TOLERANCE:
            conflicts.append(
                AllocationConflict(
                    kind=CONFLICT_SUM_NOT_100,
                    message=(
                        f"A soma dos alvos das regras detalhadas por classe é "
                        f"{total * 100:.1f}%, não 100%. Regras parciais são permitidas "
                        "(você pode configurar só algumas classes de propósito) — "
                        "mas se a intenção era cobrir a carteira inteira, confira se "
                        "falta alguma classe."
                    ),
                )
            )

    for r in rules:
        if (
            r.min_weight is not None
            and r.target_weight is not None
            and r.min_weight > r.target_weight
        ):
            conflicts.append(
                AllocationConflict(
                    kind=CONFLICT_MIN_GREATER_THAN_TARGET,
                    message=(
                        f"{r.dimension_type}='{r.dimension_key}': o mínimo "
                        f"({r.min_weight * 100:.1f}%) é maior que o alvo "
                        f"({r.target_weight * 100:.1f}%). Edite a regra para corrigir."
                    ),
                )
            )

    return conflicts
