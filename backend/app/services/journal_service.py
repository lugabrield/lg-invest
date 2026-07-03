"""Serviço do Investment Journal (Volume 12, versão MVP).

Camada fina sobre o repositório para uso pela interface: registrar uma
tese/decisão e listar entradas. Regras de validação ficam nos schemas.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.journal_entry import JournalEntry
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.journal_repository import JournalRepository
from backend.app.schemas.journal_entry import JournalEntryCreate


class JournalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = JournalRepository(db)
        self.assets = AssetRepository(db)

    def add_entry(self, payload: JournalEntryCreate) -> JournalEntry:
        return self.repo.create(
            JournalEntry(
                date=payload.date,
                asset_id=payload.asset_id,
                action=payload.action,
                thesis=payload.thesis,
                expected_outcome=payload.expected_outcome,
            )
        )

    def add_by_ticker(
        self,
        ticker: str,
        action: str,
        thesis: str,
        entry_date: date,
        expected_outcome: str | None = None,
    ) -> JournalEntry | None:
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None
        payload = JournalEntryCreate(
            date=entry_date,
            asset_id=asset.id,
            action=action,
            thesis=thesis,
            expected_outcome=expected_outcome,
        )
        return self.add_entry(payload)

    def list_all(self) -> list[JournalEntry]:
        return self.db.query(JournalEntry).order_by(JournalEntry.date.desc()).all()
