"""Repositório de TargetAllocationRule (Sprint 24, Fase 3)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.target_allocation_rule import (
    TargetAllocationRule,
)


class TargetAllocationRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_portfolio(self, portfolio_id: int) -> list[TargetAllocationRule]:
        return (
            self.db.query(TargetAllocationRule)
            .filter(TargetAllocationRule.portfolio_id == portfolio_id)
            .order_by(TargetAllocationRule.dimension_type, TargetAllocationRule.dimension_key)
            .all()
        )

    def get(
        self, portfolio_id: int, dimension_type: str, dimension_key: str
    ) -> TargetAllocationRule | None:
        return (
            self.db.query(TargetAllocationRule)
            .filter(
                TargetAllocationRule.portfolio_id == portfolio_id,
                TargetAllocationRule.dimension_type == dimension_type,
                TargetAllocationRule.dimension_key == dimension_key,
            )
            .one_or_none()
        )

    def upsert(self, rule: TargetAllocationRule) -> TargetAllocationRule:
        existing = self.get(rule.portfolio_id, rule.dimension_type, rule.dimension_key)
        if existing is not None:
            existing.min_weight = rule.min_weight
            existing.target_weight = rule.target_weight
            existing.max_weight = rule.max_weight
            existing.priority = rule.priority
            self.db.commit()
            self.db.refresh(existing)
            return existing
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete(self, portfolio_id: int, dimension_type: str, dimension_key: str) -> bool:
        rule = self.get(portfolio_id, dimension_type, dimension_key)
        if rule is None:
            return False
        self.db.delete(rule)
        self.db.commit()
        return True
