"""Testes de persistência de Asset (Volume 16, seção 14)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.repositories.asset_repository import AssetRepository


def test_create_asset(db_session):
    repo = AssetRepository(db_session)
    asset = repo.create(
        Asset(
            ticker="WEGE3.SA",
            name="WEG",
            asset_class="stock",
            country="BR",
            currency="BRL",
            sector="Industrial",
        )
    )
    assert asset.id is not None
    assert asset.is_active is True


def test_get_asset_by_ticker(db_session):
    repo = AssetRepository(db_session)
    repo.create(
        Asset(
            ticker="VOO",
            name="Vanguard S&P 500 ETF",
            asset_class="etf",
            country="US",
            currency="USD",
        )
    )
    found = repo.get_by_ticker("voo")  # busca case-insensitive
    assert found is not None
    assert found.ticker == "VOO"


def test_duplicate_ticker_raises_integrity_error(db_session):
    repo = AssetRepository(db_session)
    repo.create(
        Asset(
            ticker="ITUB4.SA",
            name="Itaú Unibanco",
            asset_class="stock",
            country="BR",
            currency="BRL",
        )
    )
    with pytest.raises(IntegrityError):
        repo.create(
            Asset(
                ticker="ITUB4.SA",
                name="Itaú Unibanco (duplicado)",
                asset_class="stock",
                country="BR",
                currency="BRL",
            )
        )


def test_list_active_excludes_inactive(db_session):
    repo = AssetRepository(db_session)
    repo.create(
        Asset(ticker="ACTIVE1", name="A", asset_class="stock", country="BR", currency="BRL")
    )
    repo.create(
        Asset(
            ticker="INACTIVE1",
            name="B",
            asset_class="stock",
            country="BR",
            currency="BRL",
            is_active=False,
        )
    )
    active = repo.list_active()
    tickers = {a.ticker for a in active}
    assert "ACTIVE1" in tickers
    assert "INACTIVE1" not in tickers
