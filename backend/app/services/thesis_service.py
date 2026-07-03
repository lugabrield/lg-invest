"""Serviço do Investment Memory (Volume 12).

Encapsula as regras de tese:
- criar tese (status inicial 'open');
- revisar tese: cria uma ThesisReview imutável e atualiza o status da
  tese conforme a classificação da revisão (sem apagar histórico);
- registrar Decision Snapshot a partir do LG Score/preço/peso atuais.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.decision_snapshot import DecisionSnapshot
from backend.app.infrastructure.database.models.investment_thesis import InvestmentThesis
from backend.app.infrastructure.database.models.thesis_review import ThesisReview
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.snapshot_repository import SnapshotRepository
from backend.app.infrastructure.repositories.thesis_repository import ThesisRepository
from backend.app.schemas.thesis import ThesisCreate, ThesisReviewCreate

# Mapeia a classificação de uma revisão para o status resultante da tese.
_CLASSIFICATION_TO_STATUS = {
    "confirmed": "confirmed",
    "partially_confirmed": "partially_confirmed",
    "in_observation": "open",
    "invalidated": "invalidated",
}


class ThesisService:
    def __init__(self, db: Session):
        self.db = db
        self.theses = ThesisRepository(db)
        self.snapshots = SnapshotRepository(db)
        self.assets = AssetRepository(db)

    def create_thesis(self, payload: ThesisCreate) -> InvestmentThesis:
        thesis = InvestmentThesis(
            asset_id=payload.asset_id,
            thesis_date=payload.thesis_date,
            status=payload.status,
            entry_price=payload.entry_price,
            hypothesis=payload.hypothesis,
            return_drivers=payload.return_drivers,
            main_risks=payload.main_risks,
            horizon=payload.horizon,
            review_criteria=payload.review_criteria,
        )
        return self.theses.create(thesis)

    def review_thesis(self, payload: ThesisReviewCreate) -> ThesisReview | None:
        """Cria uma revisão e atualiza o status da tese conforme a classificação."""
        thesis = self.theses.get_by_id(payload.thesis_id)
        if thesis is None:
            return None

        review = ThesisReview(
            thesis_id=payload.thesis_id,
            review_date=payload.review_date,
            classification=payload.classification,
            notes=payload.notes,
        )
        self.db.add(review)

        new_status = _CLASSIFICATION_TO_STATUS.get(payload.classification)
        if new_status is not None:
            thesis.status = new_status

        self.db.commit()
        self.db.refresh(review)
        return review

    def create_snapshot(
        self,
        asset_id: int,
        snapshot_date: date,
        price=None,
        current_weight=None,
        lg_score=None,
        confidence=None,
        recommended_amount=None,
        model_version=None,
        context=None,
    ) -> DecisionSnapshot:
        return self.snapshots.create(
            DecisionSnapshot(
                asset_id=asset_id,
                snapshot_date=snapshot_date,
                price=price,
                current_weight=current_weight,
                lg_score=lg_score,
                confidence=confidence,
                recommended_amount=recommended_amount,
                model_version=model_version,
                context=context,
            )
        )

    def list_theses(self) -> list[InvestmentThesis]:
        return self.theses.list_all()

    def create_by_ticker(self, ticker: str, payload_kwargs: dict) -> InvestmentThesis | None:
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None
        payload = ThesisCreate(asset_id=asset.id, **payload_kwargs)
        return self.create_thesis(payload)
