"""Repositório de Position."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.position import Position


class PositionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, position_id: int) -> Position | None:
        return self.db.get(Position, position_id)

    def get_by_portfolio_and_asset(self, portfolio_id: int, asset_id: int) -> Position | None:
        return (
            self.db.query(Position)
            .filter(Position.portfolio_id == portfolio_id, Position.asset_id == asset_id)
            .first()
        )

    def list_by_portfolio(self, portfolio_id: int) -> list[Position]:
        return self.db.query(Position).filter(Position.portfolio_id == portfolio_id).all()

    def create(self, position: Position) -> Position:
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        return position
