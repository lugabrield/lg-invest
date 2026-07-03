"""Repositório de Asset — isola acesso ao banco (Volume 16, seção 8)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.asset import Asset


class AssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, asset_id: int) -> Asset | None:
        return self.db.get(Asset, asset_id)

    def get_by_ticker(self, ticker: str) -> Asset | None:
        return self.db.query(Asset).filter(Asset.ticker == ticker.upper()).first()

    def list_active(self) -> list[Asset]:
        return self.db.query(Asset).filter(Asset.is_active.is_(True)).all()

    def list_all(self) -> list[Asset]:
        return self.db.query(Asset).all()

    def create(self, asset: Asset) -> Asset:
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset
