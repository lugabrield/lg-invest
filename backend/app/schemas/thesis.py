"""Schemas Pydantic de tese e revisão (Volume 12)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.investment_thesis import THESIS_STATUSES
from backend.app.infrastructure.database.models.thesis_review import REVIEW_CLASSIFICATIONS


class ThesisCreate(BaseModel):
    asset_id: int
    thesis_date: date
    hypothesis: str = Field(..., min_length=1)
    entry_price: Decimal | None = None
    return_drivers: str | None = None
    main_risks: str | None = None
    horizon: str | None = None
    review_criteria: str | None = None
    status: str = "open"

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in THESIS_STATUSES:
            raise ValueError(f"status inválido: {value}")
        return value


class ThesisRead(BaseModel):
    id: int
    asset_id: int
    thesis_date: date
    status: str
    entry_price: Decimal | None
    hypothesis: str
    return_drivers: str | None
    main_risks: str | None
    horizon: str | None
    review_criteria: str | None

    model_config = {"from_attributes": True}


class ThesisReviewCreate(BaseModel):
    thesis_id: int
    review_date: date
    classification: str
    notes: str | None = None

    @field_validator("classification")
    @classmethod
    def classification_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in REVIEW_CLASSIFICATIONS:
            raise ValueError(f"classification inválida: {value}")
        return value


class ThesisReviewRead(BaseModel):
    id: int
    thesis_id: int
    review_date: date
    classification: str
    notes: str | None

    model_config = {"from_attributes": True}
