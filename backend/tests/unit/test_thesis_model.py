"""Testes de persistência das entidades de memória (Volume 12)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.investment_thesis import InvestmentThesis
from backend.app.infrastructure.database.models.thesis_review import ThesisReview
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.thesis_repository import ThesisRepository


def _asset(db_session) -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )


def test_create_thesis_default_status(db_session):
    asset = _asset(db_session)
    repo = ThesisRepository(db_session)
    thesis = repo.create(
        InvestmentThesis(
            asset_id=asset.id,
            thesis_date=date(2026, 1, 5),
            hypothesis="Empresa de qualidade com crescimento consistente.",
        )
    )
    assert thesis.id is not None
    assert thesis.status == "open"


def test_thesis_with_full_fields(db_session):
    asset = _asset(db_session)
    repo = ThesisRepository(db_session)
    thesis = repo.create(
        InvestmentThesis(
            asset_id=asset.id,
            thesis_date=date(2026, 1, 5),
            hypothesis="Moat forte.",
            entry_price=Decimal("38.20"),
            return_drivers="Crescimento internacional.",
            main_risks="Valuation exigente.",
            horizon="5+ anos",
            review_criteria="Reavaliar se LG Score < 75.",
        )
    )
    assert thesis.entry_price == Decimal("38.20")
    assert thesis.horizon == "5+ anos"


def test_review_linked_to_thesis(db_session):
    asset = _asset(db_session)
    repo = ThesisRepository(db_session)
    thesis = repo.create(
        InvestmentThesis(asset_id=asset.id, thesis_date=date(2026, 1, 5), hypothesis="x")
    )
    review = ThesisReview(
        thesis_id=thesis.id,
        review_date=date(2026, 6, 1),
        classification="confirmed",
        notes="Resultados acima do esperado.",
    )
    db_session.add(review)
    db_session.commit()
    db_session.refresh(thesis)
    assert len(thesis.reviews) == 1
    assert thesis.reviews[0].classification == "confirmed"


def test_list_theses_by_asset(db_session):
    asset = _asset(db_session)
    repo = ThesisRepository(db_session)
    repo.create(InvestmentThesis(asset_id=asset.id, thesis_date=date(2025, 1, 1), hypothesis="a"))
    repo.create(InvestmentThesis(asset_id=asset.id, thesis_date=date(2026, 1, 1), hypothesis="b"))
    theses = repo.list_by_asset(asset.id)
    assert len(theses) == 2
    assert theses[0].thesis_date == date(2026, 1, 1)  # mais recente primeiro
