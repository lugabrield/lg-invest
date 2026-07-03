"""Repositório de Recommendation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.recommendation import Recommendation


class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_date(self, recommendation_date) -> list[Recommendation]:
        return (
            self.db.query(Recommendation).filter(Recommendation.date == recommendation_date).all()
        )

    def create(self, recommendation: Recommendation) -> Recommendation:
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        return recommendation
