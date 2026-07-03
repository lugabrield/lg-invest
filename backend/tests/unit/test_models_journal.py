"""Testes de persistência de JournalEntry (Volume 16, seção 14 / Volume 12)."""

from __future__ import annotations

from datetime import date

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.journal_entry import JournalEntry
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.journal_repository import JournalRepository


def test_register_thesis(db_session):
    asset = AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    repo = JournalRepository(db_session)
    entry = repo.create(
        JournalEntry(
            date=date(2026, 1, 5),
            asset_id=asset.id,
            action="buy",
            thesis="Empresa de qualidade com crescimento consistente e margem saudável.",
            expected_outcome="Manter por décadas, reavaliar apenas se fundamentos mudarem.",
        )
    )
    assert entry.id is not None
    assert entry.action == "buy"


def test_list_entries_by_asset_ordered_desc(db_session):
    asset = AssetRepository(db_session).create(
        Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    )
    repo = JournalRepository(db_session)
    repo.create(
        JournalEntry(
            date=date(2025, 1, 1), asset_id=asset.id, action="buy", thesis="Compra inicial."
        )
    )
    repo.create(
        JournalEntry(
            date=date(2026, 1, 1),
            asset_id=asset.id,
            action="thesis_review",
            thesis="Tese revisada.",
        )
    )
    entries = repo.list_by_asset(asset.id)
    assert len(entries) == 2
    assert entries[0].date == date(2026, 1, 1)  # mais recente primeiro
