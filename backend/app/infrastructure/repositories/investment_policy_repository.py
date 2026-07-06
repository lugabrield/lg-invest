"""Repositório de InvestmentPolicy (Sprint 24, Fase 3)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.investment_policy import InvestmentPolicy


class InvestmentPolicyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_portfolio(self, portfolio_id: int) -> InvestmentPolicy | None:
        return (
            self.db.query(InvestmentPolicy)
            .filter(InvestmentPolicy.portfolio_id == portfolio_id)
            .one_or_none()
        )

    def create(self, policy: InvestmentPolicy) -> InvestmentPolicy:
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def update(self, policy: InvestmentPolicy) -> InvestmentPolicy:
        self.db.commit()
        self.db.refresh(policy)
        return policy
