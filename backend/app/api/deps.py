"""Dependências compartilhadas da API HTTP (v1.1, Fase 2).

Nenhuma regra de negócio vive aqui — só wiring de sessão de banco e do
`portfolio_id` (query param), no mesmo espírito de `frontend/streamlit_app/db.py`.
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Query
from sqlalchemy.orm import Session

from backend.app.infrastructure.database.session import SessionLocal

# v1.1 continua single-user/single-portfolio por padrão (ver docs/API_CONTRACT.md
# e docs/V1_1_MIGRATION_PLAN.md) — o parâmetro já existe na API para não
# fechar a porta a multi-portfólio depois, mas hoje só a carteira 1 é usada.
DEFAULT_PORTFOLIO_ID = 1


def get_db() -> Generator[Session, None, None]:
    """Uma sessão de banco por request — igual ao `session_scope()` do Streamlit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_portfolio_id(portfolio_id: int = Query(default=DEFAULT_PORTFOLIO_ID, ge=1)) -> int:
    return portfolio_id
