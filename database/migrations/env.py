"""Configuração de execução do Alembic para a LG INVEST.

Aponta a URL de conexão para `settings.database_url` (lida do .env via
backend.app.core.config) e o target_metadata para Base.metadata, de
forma que `alembic revision --autogenerate` enxergue todas as entidades
registradas em backend/app/infrastructure/database/models.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Garante que o pacote `backend` seja importável quando o Alembic for
# executado a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.core.config import settings  # noqa: E402
from backend.app.infrastructure.database.base import Base  # noqa: E402
from backend.app.infrastructure.database.models import (  # noqa: E402,F401
    Asset,
    JournalEntry,
    Portfolio,
    Position,
    Price,
    Recommendation,
)

config = context.config

# Sobrescreve a URL do alembic.ini com a URL real do projeto (.env).
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
