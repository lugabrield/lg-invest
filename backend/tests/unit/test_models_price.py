"""Testes de persistência de Price (Volume 16, seção 14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository


def _create_asset(db_session) -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )


def test_insert_daily_price(db_session):
    asset = _create_asset(db_session)
    repo = PriceRepository(db_session)
    price = repo.create(Price(asset_id=asset.id, date=date(2026, 1, 2), close=Decimal("40.50")))
    assert price.id is not None
    assert price.close == Decimal("40.50")


def test_duplicate_asset_date_raises_integrity_error(db_session):
    asset = _create_asset(db_session)
    repo = PriceRepository(db_session)
    repo.create(Price(asset_id=asset.id, date=date(2026, 1, 2), close=Decimal("40.50")))
    with pytest.raises(IntegrityError):
        repo.create(Price(asset_id=asset.id, date=date(2026, 1, 2), close=Decimal("41.00")))


def test_get_latest_price(db_session):
    asset = _create_asset(db_session)
    repo = PriceRepository(db_session)
    repo.create(Price(asset_id=asset.id, date=date(2026, 1, 2), close=Decimal("40.50")))
    repo.create(Price(asset_id=asset.id, date=date(2026, 1, 3), close=Decimal("41.20")))
    latest = repo.get_latest(asset.id)
    assert latest.date == date(2026, 1, 3)
    assert latest.close == Decimal("41.20")
