"""Serviço do Portfolio Engine.

Fronteira entre banco e engine: lê posições da carteira, resolve o
último preço de cada ativo e monta os `PositionInput` que a engine
pura consome. Toda a parte "suja" (SQLAlchemy, último preço) vive aqui;
o cálculo vive na engine.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.portfolio.engine import build_summary
from backend.app.engines.portfolio.inputs import PositionInput
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.portfolio_summary import PortfolioSummary


class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.positions = PositionRepository(db)
        self.assets = AssetRepository(db)
        self.prices = PriceRepository(db)

    def build_inputs(self, portfolio_id: int) -> list[PositionInput]:
        """Lê posições + último preço e devolve os inputs tratados da engine."""
        inputs: list[PositionInput] = []
        for position in self.positions.list_by_portfolio(portfolio_id):
            asset = self.assets.get_by_id(position.asset_id)
            if asset is None:
                continue
            latest = self.prices.get_latest(asset.id)
            current_price = latest.close if latest is not None else None
            inputs.append(
                PositionInput(
                    ticker=asset.ticker,
                    asset_class=asset.asset_class,
                    currency=position.currency,
                    quantity=position.quantity,
                    average_price=position.average_price,
                    current_price=current_price,
                )
            )
        return inputs

    def get_summary(self, portfolio_id: int) -> PortfolioSummary:
        """Monta os inputs e retorna o resumo calculado pela engine."""
        return build_summary(self.build_inputs(portfolio_id))
