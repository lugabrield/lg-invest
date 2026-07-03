"""Sessão de banco de dados da LG INVEST.

Cria o engine SQLAlchemy a partir de `settings.database_url` e expõe
uma factory de sessões. Nenhuma regra de negócio vive aqui — apenas
infraestrutura de acesso ao banco (Volume 14 / Volume 16).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


def _build_engine_kwargs(database_url: str) -> dict:
    """SQLite local precisa de check_same_thread=False para uso
    fora da thread principal (ex.: Streamlit). PostgreSQL não precisa."""
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(
    settings.database_url,
    **_build_engine_kwargs(settings.database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager para obter uma sessão de banco com fechamento garantido.

    Uso:
        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
