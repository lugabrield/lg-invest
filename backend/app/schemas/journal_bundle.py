"""Schemas de apresentação do Investment Journal (v1.1, Fase 9).

`JournalEntryRead` e `ThesisRead`/`ThesisReviewRead`
(`backend/app/schemas/journal_entry.py`, `backend/app/schemas/thesis.py`)
já são 1:1 Pydantic, mas nenhum deles carrega o `ticker` do ativo — só
`asset_id`, porque o MVP nunca precisou disso na tela Streamlit (que já
tinha o `ticker` em mãos via `st.selectbox`). Estas views acrescentam
`ticker` (resolvido em `backend/app/api/routes/journal.py` via
`AssetRepository`, sem duplicar nenhuma regra de negócio) para a API
não obrigar o frontend a fazer um segundo lookup por `asset_id`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from backend.app.infrastructure.database.models.journal_entry import JOURNAL_ACTIONS
from backend.app.infrastructure.database.models.thesis_review import REVIEW_CLASSIFICATIONS


class JournalEntryView(BaseModel):
    """Entrada de diário, com o ticker do ativo já resolvido."""

    id: int
    date: date
    asset_id: int
    ticker: str
    action: str
    thesis: str
    expected_outcome: str | None

    model_config = {"from_attributes": True}


class JournalEntryCreateByTicker(BaseModel):
    """Payload de `POST /api/journal` — mesmos campos do formulário
    "Nova entrada de diário" do Streamlit, por ticker (não `asset_id`)."""

    ticker: str
    action: str
    date: date
    thesis: str = Field(..., min_length=1)
    expected_outcome: str | None = None

    @field_validator("action")
    @classmethod
    def action_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in JOURNAL_ACTIONS:
            raise ValueError(f"action deve ser um de: {', '.join(JOURNAL_ACTIONS)}")
        return value


class ThesisView(BaseModel):
    """Tese de investimento, com o ticker do ativo já resolvido."""

    id: int
    asset_id: int
    ticker: str
    thesis_date: date
    status: str
    entry_price: Decimal | None
    hypothesis: str
    return_drivers: str | None
    main_risks: str | None
    horizon: str | None
    review_criteria: str | None

    model_config = {"from_attributes": True}


class ThesisCreateByTicker(BaseModel):
    """Payload de `POST /api/theses` — mesmos campos do formulário "Nova
    tese de investimento" do Streamlit. `status` nunca é escolhido aqui
    (sempre nasce "open", igual ao Streamlit) — só muda via revisão."""

    ticker: str
    thesis_date: date
    hypothesis: str = Field(..., min_length=1)
    entry_price: Decimal | None = None
    return_drivers: str | None = None
    main_risks: str | None = None
    horizon: str | None = None
    review_criteria: str | None = None


class ThesisReviewView(BaseModel):
    """Revisão de uma tese, exatamente como `ThesisReviewRead`."""

    id: int
    thesis_id: int
    review_date: date
    classification: str
    notes: str | None

    model_config = {"from_attributes": True}


class ThesisReviewCreateRequest(BaseModel):
    """Payload de `POST /api/theses/{thesis_id}/reviews` — `thesis_id`
    vem da URL, não do corpo (evita divergência entre os dois)."""

    review_date: date
    classification: str
    notes: str | None = None

    @field_validator("classification")
    @classmethod
    def classification_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in REVIEW_CLASSIFICATIONS:
            raise ValueError(f"classification inválida: {value}")
        return value
