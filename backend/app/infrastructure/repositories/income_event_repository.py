"""Repositório de IncomeEvent (Sprint 23.2).

`exists_duplicate` implementa a chave de deduplicação sugerida pelo
usuário: `portfolio_id + ticker + payment_date + event_type +
amount_total + source`. Comparação feita em Python (não em SQL) para
lidar corretamente com `Decimal`/`None` sem depender de peculiaridades
de cada dialeto de banco (SQLite local vs Postgres/Supabase).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.income_event import IncomeEvent


class IncomeEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_portfolio(self, portfolio_id: int) -> list[IncomeEvent]:
        return (
            self.db.query(IncomeEvent)
            .filter(IncomeEvent.portfolio_id == portfolio_id)
            .order_by(IncomeEvent.payment_date.is_(None), IncomeEvent.payment_date.desc())
            .all()
        )

    def exists_duplicate(
        self,
        *,
        portfolio_id: int,
        ticker: str | None,
        payment_date: date | None,
        event_type: str,
        amount_total: Decimal,
        source: str,
    ) -> bool:
        existing = (
            self.db.query(IncomeEvent)
            .filter(
                IncomeEvent.portfolio_id == portfolio_id,
                IncomeEvent.ticker == ticker,
                IncomeEvent.payment_date == payment_date,
                IncomeEvent.event_type == event_type,
                IncomeEvent.source == source,
            )
            .all()
        )
        return any(row.amount_total == amount_total for row in existing)

    def create(self, event: IncomeEvent) -> IncomeEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
