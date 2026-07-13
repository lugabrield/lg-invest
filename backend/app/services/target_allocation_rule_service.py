"""Serviço de CRUD para TargetAllocationRule (Sprint 24, Fase 3).

Nenhuma regra é criada automaticamente com valor inventado — o usuário
cadastra explicitamente cada meta (por classe, moeda, país ou ativo) em
Configurações. Ver `docs/TARGET_ALLOCATION_ENGINE.md`.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.target_allocation_rule import (
    TARGET_ALLOCATION_DIMENSIONS,
    TargetAllocationRule,
)
from backend.app.infrastructure.repositories.target_allocation_rule_repository import (
    TargetAllocationRuleRepository,
)


class TargetAllocationRuleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TargetAllocationRuleRepository(db)

    def list_rules(self, portfolio_id: int) -> list[TargetAllocationRule]:
        return self.repo.list_by_portfolio(portfolio_id)

    def set_rule(
        self,
        portfolio_id: int,
        *,
        dimension_type: str,
        dimension_key: str,
        min_weight: Decimal | None = None,
        target_weight: Decimal | None = None,
        max_weight: Decimal | None = None,
        priority: int = 0,
    ) -> TargetAllocationRule:
        if dimension_type not in TARGET_ALLOCATION_DIMENSIONS:
            raise ValueError(
                f"dimension_type inválido: {dimension_type!r} "
                f"(esperado um de {TARGET_ALLOCATION_DIMENSIONS})"
            )
        dimension_key = dimension_key.strip()
        if not dimension_key:
            raise ValueError("dimension_key não pode ser vazio")

        for label, value in (
            ("min_weight", min_weight),
            ("target_weight", target_weight),
            ("max_weight", max_weight),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} não pode ser negativo")

        if min_weight is not None and max_weight is not None and min_weight > max_weight:
            raise ValueError("min_weight não pode ser maior que max_weight")
        if target_weight is not None and max_weight is not None and target_weight > max_weight:
            raise ValueError("target_weight não pode ser maior que max_weight")
        # Ajuste UX Configurações/alocação (pós-Sprint 25): min > target também
        # é um estado inconsistente (o "mínimo aceitável" não pode ficar acima
        # do "alvo desejado") — faltava esta checagem, só min > max e
        # target > max eram bloqueados antes.
        if min_weight is not None and target_weight is not None and min_weight > target_weight:
            raise ValueError("min_weight não pode ser maior que target_weight")

        rule = TargetAllocationRule(
            portfolio_id=portfolio_id,
            dimension_type=dimension_type,
            dimension_key=dimension_key,
            min_weight=min_weight,
            target_weight=target_weight,
            max_weight=max_weight,
            priority=priority,
        )
        return self.repo.upsert(rule)

    def delete_rule(self, portfolio_id: int, dimension_type: str, dimension_key: str) -> bool:
        return self.repo.delete(portfolio_id, dimension_type, dimension_key)
