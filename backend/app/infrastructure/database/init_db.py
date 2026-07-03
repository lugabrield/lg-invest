"""Inicialização rápida do banco SQLite para desenvolvimento.

Em desenvolvimento, `create_all()` é suficiente para criar as tabelas.
Em produção (e sempre que o schema mudar), a fonte de verdade é o
Alembic — nunca alterar o banco manualmente (Volume 16 / Volume 19).
"""

from __future__ import annotations

from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (  # noqa: F401  (registra as entidades)
    Asset,
    JournalEntry,
    Portfolio,
    Position,
    Price,
    Recommendation,
)
from backend.app.infrastructure.database.session import engine

logger = get_logger("lg_invest.init_db")


def init_db() -> None:
    """Cria todas as tabelas declaradas em Base.metadata, se não existirem."""
    Base.metadata.create_all(bind=engine)
    logger.info("Banco inicializado: %s tabela(s).", len(Base.metadata.tables))


if __name__ == "__main__":
    configure_logging()
    init_db()
