"""Repositório de teses de investimento."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.investment_thesis import InvestmentThesis


class ThesisRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, thesis_id: int) -> InvestmentThesis | None:
        return self.db.get(InvestmentThesis, thesis_id)

    def list_by_asset(self, asset_id: int) -> list[InvestmentThesis]:
        return (
            self.db.query(InvestmentThesis)
            .filter(InvestmentThesis.asset_id == asset_id)
            .order_by(InvestmentThesis.thesis_date.desc())
            .all()
        )

    def list_all(self) -> list[InvestmentThesis]:
        return self.db.query(InvestmentThesis).order_by(InvestmentThesis.thesis_date.desc()).all()

    def create(self, thesis: InvestmentThesis) -> InvestmentThesis:
        self.db.add(thesis)
        self.db.commit()
        self.db.refresh(thesis)
        return thesis

    def update(self, thesis: InvestmentThesis) -> InvestmentThesis:
        self.db.commit()
        self.db.refresh(thesis)
        return thesis
