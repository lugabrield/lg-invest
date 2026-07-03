"""Fixtures compartilhadas dos testes de modelo.

Usa SQLite em memória, totalmente isolado do banco real de
desenvolvimento (`data/lg_invest.db`). Cada teste recebe uma sessão
limpa, com as tabelas recriadas do zero.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (  # noqa: F401
    Asset,
    JournalEntry,
    Portfolio,
    Position,
    Price,
    Recommendation,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
