"""Repositório de Portfolio."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.portfolio import Portfolio


class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, portfolio_id: int) -> Portfolio | None:
        return self.db.get(Portfolio, portfolio_id)

    def list_all(self) -> list[Portfolio]:
        return self.db.query(Portfolio).all()

    def create(self, portfolio: Portfolio) -> Portfolio:
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio
