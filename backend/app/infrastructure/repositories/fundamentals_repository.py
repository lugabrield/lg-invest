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
