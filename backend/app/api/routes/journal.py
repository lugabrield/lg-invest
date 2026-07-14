"""Rotas do Investment Journal — diário, teses e revisões (v1.1, Fase 9
— ver docs/API_CONTRACT.md).

Consome `JournalService` (diário) e `ThesisService` (teses/revisões),
exatamente como `frontend/streamlit_app/pages_impl/journal.py` já
fazia. Nenhum cálculo financeiro vive aqui — as views só acrescentam o
`ticker` do ativo (via `AssetRepository`) ao que os services já
devolvem. Journal e teses não são escopados por `portfolio_id` (os
modelos não têm essa coluna, só `asset_id`) — mesmo comportamento do
Streamlit, que também nunca filtrou por carteira aqui.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.infrastructure.database.models import InvestmentThesis, JournalEntry
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.journal_bundle import (
    JournalEntryCreateByTicker,
    JournalEntryView,
    ThesisCreateByTicker,
    ThesisReviewCreateRequest,
    ThesisReviewView,
    ThesisView,
)
from backend.app.schemas.thesis import ThesisReviewCreate
from backend.app.services.journal_service import JournalService
from backend.app.services.thesis_service import ThesisService

router = APIRouter(tags=["journal"])


def _ticker_map(db: Session) -> dict[int, str]:
    return {asset.id: asset.ticker for asset in AssetRepository(db).list_all()}


def _journal_view(entry: JournalEntry, tickers: dict[int, str]) -> JournalEntryView:
    return JournalEntryView(
        id=entry.id,
        date=entry.date,
        asset_id=entry.asset_id,
        ticker=tickers.get(entry.asset_id, "?"),
        action=entry.action,
        thesis=entry.thesis,
        expected_outcome=entry.expected_outcome,
    )


def _thesis_view(thesis: InvestmentThesis, tickers: dict[int, str]) -> ThesisView:
    return ThesisView(
        id=thesis.id,
        asset_id=thesis.asset_id,
        ticker=tickers.get(thesis.asset_id, "?"),
        thesis_date=thesis.thesis_date,
        status=thesis.status,
        entry_price=thesis.entry_price,
        hypothesis=thesis.hypothesis,
        return_drivers=thesis.return_drivers,
        main_risks=thesis.main_risks,
        horizon=thesis.horizon,
        review_criteria=thesis.review_criteria,
    )


@router.get("/journal", response_model=list[JournalEntryView])
def list_journal_entries(db: Session = Depends(get_db)) -> list[JournalEntryView]:
    tickers = _ticker_map(db)
    entries = JournalService(db).list_all()
    return [_journal_view(entry, tickers) for entry in entries]


@router.post("/journal", response_model=JournalEntryView, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreateByTicker, db: Session = Depends(get_db)
) -> JournalEntryView:
    entry = JournalService(db).add_by_ticker(
        ticker=payload.ticker,
        action=payload.action,
        thesis=payload.thesis,
        entry_date=payload.date,
        expected_outcome=payload.expected_outcome,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Ativo '{payload.ticker}' não encontrado.")
    return _journal_view(entry, _ticker_map(db))


@router.get("/theses", response_model=list[ThesisView])
def list_theses(db: Session = Depends(get_db)) -> list[ThesisView]:
    tickers = _ticker_map(db)
    theses = ThesisService(db).list_theses()
    return [_thesis_view(thesis, tickers) for thesis in theses]


@router.post("/theses", response_model=ThesisView, status_code=201)
def create_thesis(payload: ThesisCreateByTicker, db: Session = Depends(get_db)) -> ThesisView:
    created = ThesisService(db).create_by_ticker(
        payload.ticker,
        {
            "thesis_date": payload.thesis_date,
            "hypothesis": payload.hypothesis,
            "entry_price": payload.entry_price,
            "return_drivers": payload.return_drivers,
            "main_risks": payload.main_risks,
            "horizon": payload.horizon,
            "review_criteria": payload.review_criteria,
        },
    )
    if created is None:
        raise HTTPException(status_code=404, detail=f"Ativo '{payload.ticker}' não encontrado.")
    return _thesis_view(created, _ticker_map(db))


@router.post("/theses/{thesis_id}/reviews", response_model=ThesisReviewView, status_code=201)
def create_thesis_review(
    thesis_id: int, payload: ThesisReviewCreateRequest, db: Session = Depends(get_db)
) -> ThesisReviewView:
    review = ThesisService(db).review_thesis(
        ThesisReviewCreate(
            thesis_id=thesis_id,
            review_date=payload.review_date,
            classification=payload.classification,
            notes=payload.notes,
        )
    )
    if review is None:
        raise HTTPException(status_code=404, detail=f"Tese #{thesis_id} não encontrada.")
    return ThesisReviewView.model_validate(review)
