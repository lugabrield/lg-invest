"""Repositório de IncomeMonthlySummary (Sprint 23.3).

`exists_duplicate` implementa a chave de deduplicação combinada com
`NormalizedMonthlySummary.dedup_key`: `portfolio_id + wallet_name + year
+ month + currency + source`. Comparação feita em Python (mesmo padrão
de `IncomeEventRepository`) para lidar corretamente com `Decimal`/`None`
sem depender de peculiaridades de cada dialeto de banco.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.income_monthly_summary import (
    IncomeMonthlySummary,
)


class IncomeMonthlySummaryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_portfolio(self, portfolio_id: int) -> list[IncomeMonthlySummary]:
        return (
            self.db.query(IncomeMonthlySummary)
            .filter(IncomeMonthlySummary.portfolio_id == portfolio_id)
            .order_by(IncomeMonthlySummary.year.desc(), IncomeMonthlySummary.month.desc())
            .all()
        )

    def exists_duplicate(
        self,
        *,
        portfolio_id: int,
        wallet_name: str,
        year: int,
        month: int,
        currency: str,
        source: str,
    ) -> bool:
        existing = (
            self.db.query(IncomeMonthlySummary)
            .filter(
                IncomeMonthlySummary.portfolio_id == portfolio_id,
                IncomeMonthlySummary.wallet_name == wallet_name,
                IncomeMonthlySummary.year == year,
                IncomeMonthlySummary.month == month,
                IncomeMonthlySummary.currency == currency,
                IncomeMonthlySummary.source == source,
            )
            .all()
        )
        return len(existing) > 0

    def create(self, summary: IncomeMonthlySummary) -> IncomeMonthlySummary:
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary
