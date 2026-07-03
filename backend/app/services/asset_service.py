"""Serviço de cadastro de ativos.

Camada de aplicação que orquestra a criação/atualização de ativos
usando o AssetRepository. Mantém a regra de negócio fora dos modelos
ORM e fora da interface (Clean Architecture, Volume 14).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.asset import AssetCreate


class AssetService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AssetRepository(db)

    def create_asset(self, payload: AssetCreate) -> Asset:
        """Cria um ativo a partir de um payload já validado.

        Levanta ValueError se o ticker já existir.
        """
        if self.repo.get_by_ticker(payload.ticker):
            raise ValueError(f"Ativo já cadastrado: {payload.ticker}")
        asset = Asset(
            ticker=payload.ticker,
            name=payload.name,
            asset_class=payload.asset_class,
            country=payload.country,
            currency=payload.currency,
            sector=payload.sector,
            is_active=payload.is_active,
        )
        return self.repo.create(asset)

    def get_or_none(self, ticker: str) -> Asset | None:
        return self.repo.get_by_ticker(ticker)
