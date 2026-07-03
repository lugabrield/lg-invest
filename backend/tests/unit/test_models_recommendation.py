"""Testes de persistência de Recommendation (Volume 16, seção 14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.recommendation import Recommendation
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.recommendation_repository import (
    RecommendationRepository,
)


def test_save_recommendation_with_snapshot(db_session):
    asset = AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    repo = RecommendationRepository(db_session)
    rec = repo.create(
        Recommendation(
            date=date(2026, 1, 5),
            contribution_amount=Decimal("1000.00"),
            asset_id=asset.id,
            amount=Decimal("400.00"),
            reason="LG Score elevado e abaixo do peso-alvo na carteira.",
            algo_version="v1",
        )
    )
    assert rec.id is not None
    assert rec.algo_version == "v1"


def test_list_recommendations_by_date(db_session):
    asset = AssetRepository(db_session).create(
        Asset(
            ticker="VOO",
            name="Vanguard S&P 500 ETF",
            asset_class="etf",
            country="US",
            currency="USD",
        )
    )
    repo = RecommendationRepository(db_session)
    target_date = date(2026, 1, 5)
    repo.create(
        Recommendation(
            date=target_date,
            contribution_amount=Decimal("1000.00"),
            asset_id=asset.id,
            amount=Decimal("600.00"),
            reason="Diversificação internacional.",
        )
    )
    results = repo.list_by_date(target_date)
    assert len(results) == 1
    assert results[0].asset_id == asset.id
