"""Testes de persistência de Position (Volume 16, seção 14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.infrastructure.repositories.position_repository import PositionRepository


def _setup(db_session) -> tuple[Portfolio, Asset]:
    portfolio = PortfolioRepository(db_session).create(Portfolio(name="Carteira Principal"))
    asset = AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    return portfolio, asset


def test_create_position(db_session):
    portfolio, asset = _setup(db_session)
    repo = PositionRepository(db_session)
    position = repo.create(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            average_price=Decimal("38.20"),
            currency="BRL",
            opened_at=date(2025, 6, 1),
        )
    )
    assert position.id is not None


def test_unique_portfolio_asset(db_session):
    portfolio, asset = _setup(db_session)
    repo = PositionRepository(db_session)
    repo.create(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            average_price=Decimal("38.20"),
            currency="BRL",
            opened_at=date(2025, 6, 1),
        )
    )
    with pytest.raises(IntegrityError):
        repo.create(
            Position(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                quantity=Decimal("50"),
                average_price=Decimal("40.00"),
                currency="BRL",
                opened_at=date(2025, 7, 1),
            )
        )
