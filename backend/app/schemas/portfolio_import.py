"""Schema de saída de `POST /api/portfolio/import` (v1.1, Fase 4).

Espelha 1:1 `backend/app/etl/importers/import_result.py::ImportResult`
(dataclass) — nenhuma regra nova, só o formato serializável do resultado
que `PortfolioImportService.import_positions` já produzia para a tela
Streamlit (`pages_impl/carteira.py`).
"""

from __future__ import annotations

from pydantic import BaseModel


class ImportErrorView(BaseModel):
    line: int
    field: str | None
    message: str


class ImportResultView(BaseModel):
    total_rows: int
    imported: int
    updated: int
    skipped: int
    errors: list[ImportErrorView]
