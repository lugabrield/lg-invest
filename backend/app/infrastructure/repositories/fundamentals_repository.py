"""Repositório de FundamentalSnapshot."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot


class FundamentalsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_asset_and_period(
        self, asset_id: int, period_end: date
    ) -> FundamentalSnapshot | None:
        return (
            self.db.query(FundamentalSnapshot)
            .filter(
                FundamentalSnapshot.asset_id == asset_id,
                FundamentalSnapshot.period_end == period_end,
            )
            .first()
        )

    def list_by_asset(self, asset_id: int) -> list[FundamentalSnapshot]:
        return (
            self.db.query(FundamentalSnapshot)
            .filter(FundamentalSnapshot.asset_id == asset_id)
            .order_by(FundamentalSnapshot.period_end.asc())
            .all()
        )

    def get_latest(self, asset_id: int) -> FundamentalSnapshot | None:
        return (
            self.db.query(FundamentalSnapshot)
            .filter(FundamentalSnapshot.asset_id == asset_id)
            .order_by(FundamentalSnapshot.period_end.desc())
            .first()
        )

    def create(self, snapshot: FundamentalSnapshot) -> FundamentalSnapshot:
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def upsert_fields(
        self, asset_id: int, period_end: date, source: str, fields: dict[str, object]
    ) -> FundamentalSnapshot:
        """Cria ou atualiza o snapshot de um período com os campos dados.

        Usado pela importação manual de fundamentos (Sprint 28, Fase 5):
        `fields` só contém as colunas presentes/validadas na linha do
        arquivo — colunas ausentes no arquivo NUNCA são zeradas num
        snapshot existente (Volume 18 §8: nunca inventar/apagar dado)."""
        existing = self.get_by_asset_and_period(asset_id, period_end)
        if existing is not None:
            existing.source = source
            for key, value in fields.items():
                setattr(existing, key, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        snapshot = FundamentalSnapshot(
            asset_id=asset_id, period_end=period_end, source=source, **fields
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot
