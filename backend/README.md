# Backend — LG INVEST

Núcleo da plataforma em Python. Segue Clean Architecture: a interface não
conhece infraestrutura, e as engines financeiras nunca acessam APIs externas
diretamente (recebem dados já tratados).

## Pastas
- `app/core/` — configurações, logging, settings e exceções.
- `app/infrastructure/database/` — Base, sessão, init_db e `models/` (entidades SQLAlchemy).
- `app/infrastructure/repositories/` — Repository Pattern; isola todo acesso ao banco.
- `app/schemas/` — schemas Pydantic de entrada/saída (separados das entidades ORM).
- `app/etl/importers/` — importação de carteira via CSV/Excel (Sprint 3).
- `app/etl/providers/` — provedores de preço substituíveis (yfinance); contrato em `etl/contracts/` (Sprint 4).
- `app/etl/validators/` — validação de importação e de qualidade de preço.
- `app/engines/portfolio/` — Portfolio Engine v1: cálculo puro da carteira (Sprint 5).
- `app/engines/lg_score/` — LG Score v1: score composto por ativo, 5 pilares + confiança + explicação (Sprint 6).
- `app/engines/decision/` — Decision Engine v1: score de compra, filtro de elegibilidade, distribuição do aporte e auditoria (Sprint 7).
- `app/services/` — orquestração entre repositórios e engines.
- `tests/unit/` — testes de modelo e persistência (SQLite em memória, isolado do banco real).
- `tests/test_smoke.py` — valida que config/logging/entrypoint carregam.

## Modelos de dados (Sprint 2)

Asset, Portfolio, Position, Price, Recommendation, JournalEntry — ver `database/README.md`
para comandos de migration e seed.

