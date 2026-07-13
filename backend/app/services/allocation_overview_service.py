"""Serviço de orquestração para a visão consolidada de alocação-alvo
(ajuste UX Configurações/alocação, pós-Sprint 25).

Só lê (regras detalhadas, política geral, alocação simples) e delega o
cálculo de precedência/conflitos para `engines/target_allocation/
precedence.py` (puro). Nunca grava nada, nunca é usado pelo Decision
Engine — existe só para a tela de Configurações mostrar, de forma
explícita, qual camada está valendo em cada dimensão e onde há
inconsistência entre elas.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.target_allocation import precedence as precedence_engine
from backend.app.infrastructure.repositories.target_allocation_rule_repository import (
    TargetAllocationRuleRepository,
)
from backend.app.schemas.target_allocation import (
    AllocationConflictView,
    AllocationOverview,
    EffectiveLimitView,
)
from backend.app.services import target_allocation_settings_service
from backend.app.services.investment_policy_service import InvestmentPolicyService


def build_allocation_overview(db: Session, portfolio_id: int) -> AllocationOverview:
    rules = TargetAllocationRuleRepository(db).list_by_portfolio(portfolio_id)
    rule_inputs = [
        precedence_engine.RuleLike(
            dimension_type=r.dimension_type,
            dimension_key=r.dimension_key,
            min_weight=r.min_weight,
            target_weight=r.target_weight,
            max_weight=r.max_weight,
            priority=r.priority,
        )
        for r in rules
    ]

    policy = InvestmentPolicyService(db).get_or_create(portfolio_id)
    policy_input = precedence_engine.PolicyLike(
        max_asset_weight=policy.max_asset_weight,
        max_crypto_weight=policy.max_crypto_weight,
        target_fii_max=policy.target_fii_max,
    )

    simple_allocation = target_allocation_settings_service.get_target_allocation()

    effective_limits = precedence_engine.resolve_effective_limits(rule_inputs, policy_input)
    conflicts = precedence_engine.detect_conflicts(rule_inputs, simple_allocation)

    return AllocationOverview(
        effective_limits=[
            EffectiveLimitView(
                dimension_type=el.dimension_type,
                dimension_key=el.dimension_key,
                max_weight=el.max_weight,
                source=el.source,
                overridden_policy_value=el.overridden_policy_value,
            )
            for el in effective_limits
        ],
        conflicts=[AllocationConflictView(kind=c.kind, message=c.message) for c in conflicts],
    )
