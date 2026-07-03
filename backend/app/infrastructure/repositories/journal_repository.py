"""Repositório de JournalEntry."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.journal_entry import JournalEntry


class JournalRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_asset(self, asset_id: int) -> list[JournalEntry]:
        return (
            self.db.query(JournalEntry)
            .filter(JournalEntry.asset_id == asset_id)
            .order_by(JournalEntry.date.desc())
            .all()
        )

    def create(self, entry: JournalEntry) -> JournalEntry:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
