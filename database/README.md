# Database — LG INVEST

- `migrations/` — versionamento de schema com Alembic.
- `seeds/` — ativos de demonstração (sem dados pessoais reais).

Toda alteração estrutural gera uma migration. Nunca alterar o banco manualmente.

## Entidades do MVP (Sprint 2)

Asset, Portfolio, Position, Price, Recommendation, JournalEntry — definidas em
`backend/app/infrastructure/database/models/`. `Position` é única por
`(portfolio_id, asset_id)`: o MVP trabalha com posição consolidada, não com lotes.

## Comandos

```bash
# Criar uma nova migration a partir de mudanças nos models
python -m alembic revision --autogenerate -m "descrição da mudança"

# Aplicar migrations pendentes
python -m alembic upgrade head

# Reverter a última migration
python -m alembic downgrade -1

# Popular ativos de demonstração (idempotente)
python -m database.seeds.assets_seed

# Atalho de desenvolvimento: cria tabelas sem passar pelo Alembic
python -m backend.app.infrastructure.database.init_db
```

A URL de conexão vem de `settings.database_url` (lida do `.env`), configurada em
`database/migrations/env.py` — não editar `sqlalchemy.url` no `alembic.ini` diretamente.

