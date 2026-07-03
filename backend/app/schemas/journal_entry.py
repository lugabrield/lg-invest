"""Schemas Pydantic de JournalEntry."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.journal_entry import JOURNAL_ACTIONS


class JournalEntryCreate(BaseModel):
    date: date
    asset_id: int
    action: str
    thesis: str = Field(..., min_length=1)
    expected_outcome: str | None = None

    @field_validator("action")
    @classmethod
    def action_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in JOURNAL_ACTIONS:
            raise ValueError(f"action deve ser um de: {', '.join(JOURNAL_ACTIONS)}")
        return value


class JournalEntryRead(BaseModel):
    id: int
    date: date
    asset_id: int
    action: str
    thesis: str
    expected_outcome: str | None

    model_config = {"from_attributes": True}
