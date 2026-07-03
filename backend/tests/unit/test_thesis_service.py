"""Testes do ThesisService (Volume 12): ciclo de vida e snapshot."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.thesis import ThesisCreate, ThesisReviewCreate
from backend.app.services.thesis_service import ThesisService


def _asset(db_session) -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )


def test_create_thesis(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_thesis(
        ThesisCreate(
            asset_id=asset.id,
            thesis_date=date(2026, 1, 5),
            hypothesis="Qualidade e crescimento.",
        )
    )
    assert thesis.id is not None
    assert thesis.status == "open"


def test_review_confirmed_updates_status(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_thesis(
        ThesisCreate(asset_id=asset.id, thesis_date=date(2026, 1, 5), hypothesis="x")
    )
    service.review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis.id, review_date=date(2026, 6, 1), classification="confirmed"
        )
    )
    db_session.refresh(thesis)
    assert thesis.status == "confirmed"


def test_review_invalidated_updates_status(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_thesis(
        ThesisCreate(asset_id=asset.id, thesis_date=date(2026, 1, 5), hypothesis="x")
    )
    service.review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis.id, review_date=date(2026, 6, 1), classification="invalidated"
        )
    )
    db_session.refresh(thesis)
    assert thesis.status == "invalidated"


def test_review_history_is_preserved(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_thesis(
        ThesisCreate(asset_id=asset.id, thesis_date=date(2026, 1, 5), hypothesis="x")
    )
    service.review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis.id, review_date=date(2026, 3, 1), classification="in_observation"
        )
    )
    service.review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis.id, review_date=date(2026, 6, 1), classification="confirmed"
        )
    )
    db_session.refresh(thesis)
    # Duas revisões preservadas; status reflete a última.
    assert len(thesis.reviews) == 2
    assert thesis.status == "confirmed"


def test_review_in_observation_maps_to_open(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_thesis(
        ThesisCreate(asset_id=asset.id, thesis_date=date(2026, 1, 5), hypothesis="x")
    )
    service.review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis.id, review_date=date(2026, 6, 1), classification="in_observation"
        )
    )
    db_session.refresh(thesis)
    assert thesis.status == "open"


def test_review_unknown_thesis_returns_none(db_session):
    service = ThesisService(db_session)
    result = service.review_thesis(
        ThesisReviewCreate(thesis_id=999, review_date=date(2026, 6, 1), classification="confirmed")
    )
    assert result is None


def test_create_snapshot(db_session):
    asset = _asset(db_session)
    service = ThesisService(db_session)
    snap = service.create_snapshot(
        asset_id=asset.id,
        snapshot_date=date(2026, 1, 5),
        price=Decimal("40.00"),
        current_weight=Decimal("0.20"),
        lg_score=Decimal("82.5"),
        confidence=Decimal("0.75"),
        recommended_amount=Decimal("300.00"),
        model_version="decision_v1",
    )
    assert snap.id is not None
    assert snap.lg_score == Decimal("82.5")


def test_create_by_ticker(db_session):
    _asset(db_session)
    service = ThesisService(db_session)
    thesis = service.create_by_ticker(
        "WEGE3.SA",
        {"thesis_date": date(2026, 1, 5), "hypothesis": "Boa empresa."},
    )
    assert thesis is not None


def test_create_by_unknown_ticker_returns_none(db_session):
    service = ThesisService(db_session)
    result = service.create_by_ticker("NOPE9", {"thesis_date": date(2026, 1, 5), "hypothesis": "x"})
    assert result is None
