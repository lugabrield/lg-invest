"""Repositório de ExternalSyncRun (Sprint 23)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.external_sync_run import ExternalSyncRun


class ExternalSyncRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, run_id: int) -> ExternalSyncRun | None:
        return self.db.get(ExternalSyncRun, run_id)

    def list_by_portfolio(self, portfolio_id: int, limit: int = 20) -> list[ExternalSyncRun]:
        return (
            self.db.query(ExternalSyncRun)
            .filter(ExternalSyncRun.portfolio_id == portfolio_id)
            .order_by(ExternalSyncRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_latest(self, portfolio_id: int, provider: str) -> ExternalSyncRun | None:
        return (
            self.db.query(ExternalSyncRun)
            .filter(
                ExternalSyncRun.portfolio_id == portfolio_id,
                ExternalSyncRun.provider == provider,
                ExternalSyncRun.status == "success",
            )
            .order_by(ExternalSyncRun.created_at.desc())
            .first()
        )

    def create(self, run: ExternalSyncRun) -> ExternalSyncRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
