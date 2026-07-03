"""Repositório de Decision Snapshots."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.decision_snapshot import DecisionSnapshot


class SnapshotRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_asset(self, asset_id: int) -> list[DecisionSnapshot]:
        return (
            self.db.query(DecisionSnapshot)
            .filter(DecisionSnapshot.asset_id == asset_id)
            .order_by(DecisionSnapshot.snapshot_date.desc())
            .all()
        )

    def create(self, snapshot: DecisionSnapshot) -> DecisionSnapshot:
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot
