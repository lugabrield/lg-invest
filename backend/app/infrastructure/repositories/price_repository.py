"""Repositório de Price."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.price import Price


class PriceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_asset_and_date(self, asset_id: int, price_date: date) -> Price | None:
        return (
            self.db.query(Price)
            .filter(Price.asset_id == asset_id, Price.date == price_date)
            .first()
        )

    def list_by_asset(self, asset_id: int) -> list[Price]:
        return (
            self.db.query(Price).filter(Price.asset_id == asset_id).order_by(Price.date.asc()).all()
        )

    def get_latest(self, asset_id: int) -> Price | None:
        return (
            self.db.query(Price)
            .filter(Price.asset_id == asset_id)
            .order_by(Price.date.desc())
            .first()
        )

    def create(self, price: Price) -> Price:
        self.db.add(price)
        self.db.commit()
        self.db.refresh(price)
        return price
