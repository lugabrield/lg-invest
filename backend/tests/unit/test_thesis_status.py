"""Testes de validação de status e classificação (Volume 12, seção 7)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.schemas.thesis import ThesisCreate, ThesisReviewCreate


def test_valid_status_accepted():
    t = ThesisCreate(asset_id=1, thesis_date=date(2026, 1, 5), hypothesis="x", status="confirmed")
    assert t.status == "confirmed"


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        ThesisCreate(asset_id=1, thesis_date=date(2026, 1, 5), hypothesis="x", status="banana")


def test_status_normalized_to_lower():
    t = ThesisCreate(asset_id=1, thesis_date=date(2026, 1, 5), hypothesis="x", status="OPEN")
    assert t.status == "open"


def test_valid_classification_accepted():
    r = ThesisReviewCreate(
        thesis_id=1, review_date=date(2026, 6, 1), classification="partially_confirmed"
    )
    assert r.classification == "partially_confirmed"


def test_invalid_classification_rejected():
    with pytest.raises(ValidationError):
        ThesisReviewCreate(thesis_id=1, review_date=date(2026, 6, 1), classification="maybe")


def test_empty_hypothesis_rejected():
    with pytest.raises(ValidationError):
        ThesisCreate(asset_id=1, thesis_date=date(2026, 1, 5), hypothesis="")
