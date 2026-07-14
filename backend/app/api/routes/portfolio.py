"""Rota de importação de carteira (v1.1, Fase 4 — ver docs/API_CONTRACT.md).

`POST /api/portfolio/import` chama o mesmo `PortfolioImportService`
(inalterado) que `frontend/streamlit_app/pages_impl/carteira.py` já
usava — só troca a origem do arquivo (upload HTTP em vez de
`st.file_uploader`) e a saída (JSON em vez de `st.dataframe`). A leitura
da carteira (posições, pesos, grupos) não tem endpoint próprio: já é
coberta por `GET /api/dashboard` (`view.positions`).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.repositories.portfolio_repository import PortfolioRepository
from backend.app.schemas.portfolio_import import ImportResultView
from backend.app.services.portfolio_import_service import PortfolioImportService

router = APIRouter(tags=["portfolio"])

_ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}


def _ensure_portfolio(db: Session, portfolio_id: int) -> Portfolio:
    repo = PortfolioRepository(db)
    portfolio = repo.get_by_id(portfolio_id)
    if portfolio is None:
        portfolio = repo.create(Portfolio(name=f"Carteira {portfolio_id}"))
    return portfolio


@router.post("/portfolio/import", response_model=ImportResultView)
async def import_portfolio(
    file: UploadFile,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> ImportResultView:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"Formato não suportado ({suffix or 'sem extensão'}). Use .csv, .xlsx ou .xls.",
        )

    contents = await file.read()
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        _ensure_portfolio(db, portfolio_id)
        result = PortfolioImportService(db).import_positions(portfolio_id, tmp_path)
    finally:
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)

    return ImportResultView(**result.as_dict())
